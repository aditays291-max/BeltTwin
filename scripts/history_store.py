"""Per-splice append-only records, atomically persisted on completed inspections."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import msvcrt
from inspection_history import history_record, inspection_number, validate_history_record
from splice_tracker import SPLICES


class HistoryStore:
    def __init__(self, directory, minimum_inspection_number=0):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = None
        self._history = {s: [] for s in SPLICES}
        self.appended_count = 0
        # Keep one writer per history directory. Windows releases the lock even
        # on process termination; a leftover lock file is harmless.
        lock = (self.directory / '.writer.lock').open('a+b')
        if lock.seek(0, os.SEEK_END) == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            lock.close()
            raise RuntimeError('History already has an active writer; close the other Phase 4 run.') from error
        self._lock = lock
        try:
            for splice in SPLICES:
                path = self.directory / f'{splice}.json'
                if path.exists():
                    document = json.loads(path.read_text(encoding='utf-8'))
                    records = document['inspections']
                    if document['history_version'] != '1.0' or not isinstance(records, list) or document['splice_id'] != splice or document['inspection_count'] != len(records):
                        raise ValueError(f'Invalid history header: {path}')
                    for sequence, record in enumerate(records, 1):
                        validate_history_record(record)
                        if record['splice_id'] != splice or record['inspection_sequence'] != sequence:
                            raise ValueError(f'History identity/sequence mismatch: {path}')
                        if sequence > 1 and (record['timestamp_s'] <= records[sequence - 2]['timestamp_s'] or
                                             inspection_number(record['inspection_id']) <= inspection_number(records[sequence - 2]['inspection_id'])):
                            raise ValueError(f'History order mismatch: {path}')
                    self._history[splice] = records
            records = sorted((r for rows in self._history.values() for r in rows),
                             key=lambda r: inspection_number(r['inspection_id']))
            numbers = [inspection_number(r['inspection_id']) for r in records]
            if len(set(numbers)) != len(numbers):
                raise ValueError('Duplicate persisted inspection ID')
            if any(b['timestamp_s'] <= a['timestamp_s'] or b['run_sequence'] < a['run_sequence']
                   for a, b in zip(records, records[1:])):
                raise ValueError('History is not chronological')
            self.last_inspection_number = max(numbers + [minimum_inspection_number])
            self.time_offset = max([r['timestamp_s'] for r in records], default=0.0)
            self._last_timestamp = self.time_offset
            self.run_sequence = max([r['run_sequence'] for r in records], default=0) + 1
            self.loaded_count = len(records)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def records(self, splice):
        return deepcopy(self._history[splice])

    def counts(self):
        return {s: len(rows) for s, rows in self._history.items()}

    def append(self, record):
        if self._lock is None:
            raise RuntimeError('History store is closed')
        splice = record['splice_id']
        if splice not in SPLICES:
            raise ValueError('Unknown splice')
        number = inspection_number(record['inspection_id'])
        if number <= self.last_inspection_number:
            raise ValueError('Duplicate or out-of-order inspection ID; existing records preserved')
        observation = history_record(record, len(self._history[splice]) + 1,
                                     self.run_sequence, self.time_offset)
        if observation['timestamp_s'] <= self._last_timestamp:
            raise ValueError('Out-of-order simulation timestamp; existing records preserved')
        updated = self._history[splice] + [observation]
        document = {'history_version': '1.0', 'splice_id': splice,
                    'inspection_count': len(updated), 'inspections': updated}
        descriptor, temporary = tempfile.mkstemp(prefix='.history-', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(document, stream, indent=2, allow_nan=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            # Only the container is replaced. Every previous observation is
            # copied unchanged; there is no update/delete operation for records.
            os.replace(temporary, self.directory / f'{splice}.json')
        finally:
            Path(temporary).unlink(missing_ok=True)
        self._history[splice] = updated
        self.last_inspection_number = number
        self._last_timestamp = observation['timestamp_s']
        self.appended_count += 1
        return deepcopy(observation)
