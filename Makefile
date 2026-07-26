PACKAGE := wb-dali-ha

.PHONY: test build

test:
	python3 -m py_compile src/wb_dali_ha.py
	PYTHONPATH=src python3 tests/test_payloads.py

build:
	dpkg-buildpackage -us -uc
