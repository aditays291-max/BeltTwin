"""Create-once JSON baselines. Existing files are never replaced or repaired."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from digital_fingerprint import from_inspection, validate_fingerprint
from splice_tracker import SPLICES


class FingerprintStore:
    def __init__(self, directory, read_only=False):
        self.directory = Path(directory)
        self.read_only = read_only
        if not read_only:
            self.directory.mkdir(parents=True, exist_ok=True)
        self._fingerprints = {}
        self.created_count = 0
        self.preserved_count = 0
        for splice in SPLICES:
            path = self.directory / f'{splice}.json'
            if path.exists():
                self._fingerprints[splice] = self._load(path, splice)
        self.loaded_count = len(self._fingerprints)

    @staticmethod
    def _load(path, splice):
        try:
            fp = json.loads(path.read_text(encoding='utf-8'))
            validate_fingerprint(fp)
            if fp['splice_id'] != splice:
                raise ValueError('Filename and splice ID disagree')
            return fp
        except (ValueError, KeyError, TypeError, OSError) as error:
            raise ValueError(f'Cannot load baseline {path}; file preserved: {error}') from error

    def get(self, splice):
        if splice not in SPLICES:
            raise ValueError(f'Unknown splice: {splice}')
        # Never expose the internal mutable dictionaries or arrays.
        return deepcopy(self._fingerprints.get(splice))

    def __len__(self):
        return len(self._fingerprints)

    def remember(self, record):
        if self.read_only:
            raise PermissionError('This fingerprint store is read-only')
        splice = record['splice_id']
        if splice not in SPLICES:
            raise ValueError(f'Unknown splice: {splice}')
        if splice in self._fingerprints:
            self.preserved_count += 1
            return self.get(splice), False
        fp = from_inspection(record)
        target = self.directory / f'{splice}.json'
        # Publish a completely written file using a create-only hard link. Unlike
        # replace/rename-with-overwrite, this cannot overwrite a concurrent writer.
        descriptor, temporary = tempfile.mkstemp(prefix='.baseline-', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(fp, stream, indent=2, allow_nan=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
                created = True
            except FileExistsError:
                fp = self._load(target, splice)
                created = False
            self._fingerprints[splice] = fp
            self.created_count += int(created)
            self.preserved_count += int(not created)
            return self.get(splice), created
        finally:
            Path(temporary).unlink(missing_ok=True)
