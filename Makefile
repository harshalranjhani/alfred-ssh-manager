.PHONY: test lint build clean

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

lint:
	python3 -m compileall -q src scripts tools
	python3 -c 'import plistlib; plistlib.load(open("workflow/info.plist", "rb"))'

build:
	python3 tools/build.py

clean:
	rm -rf build dist
