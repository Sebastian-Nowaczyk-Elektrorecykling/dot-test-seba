"""Offline checks of the container declaration, not a Docker build/runtime test."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ContainerContractTests(unittest.TestCase):
    def test_base_is_exact_linux_amd64_manifest(self):
        source = (ROOT / 'Dockerfile').read_text()
        base = re.search(r'^FROM (.+)$', source, re.MULTILINE).group(1)
        self.assertEqual(base, 'python:3.12-slim-bookworm@sha256:'
                         '9901e0a8d75037d8242ed43155cbcb2d1f61be1356383d8054afb59fd50e39c4')

    def test_unprivileged_fixed_port_and_application_entrypoint(self):
        source = (ROOT / 'Dockerfile').read_text()
        self.assertIn('USER 10001:10001', source)
        self.assertIn('HOST=0.0.0.0', source)
        self.assertIn('PORT=8080', source)
        self.assertIn('PYTHONDONTWRITEBYTECODE=1', source)
        self.assertIn('COPY --chown=10001:10001 gus_app/ /app/gus_app/', source)
        self.assertIn('ENTRYPOINT ["python", "-m", "gus_app.server"]', source)
        self.assertNotRegex(source, r'(?m)^\s*(?:ADD|RUN|VOLUME)\b')
        self.assertNotIn('4103', source)  # Host port belongs to the slot controller.

    def test_build_context_is_allowlisted_and_excludes_private_local_files(self):
        rules = [line for line in (ROOT / '.dockerignore').read_text().splitlines()
                 if line and not line.startswith('#')]
        self.assertEqual(rules[0], '**')
        self.assertEqual([line for line in rules if line.startswith('!')],
                         ['!Dockerfile', '!gus_app/', '!gus_app/**'])
        self.assertIn('**/__pycache__/', rules)
        self.assertIn('**/.env', rules)
        self.assertIn('**/.env.*', rules)



if __name__ == '__main__':
    unittest.main()
