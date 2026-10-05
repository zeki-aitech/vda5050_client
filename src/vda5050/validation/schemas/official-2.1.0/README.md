# Official VDA5050 2.1.0 JSON schemas

Copied unchanged from https://github.com/VDA5050/VDA5050, tag `2.1.0`
(commit `511d01d71587e8a3dc5e71d4f41dc52466f4284c`), directory
`json_schemas/` (renamed from `<name>.schema` to `<name>.schema.json`).
Licence: `LICENSE.txt` beside this file (MIT, Verband der Automobilindustrie).

They are not used to validate messages. The schemas one directory up are,
and they are these with the corrections listed in the library's README.
`tests/unit/test_conformance.py` compares both the pydantic models and the
bundled schemas with these files, so a change on either side is seen.
