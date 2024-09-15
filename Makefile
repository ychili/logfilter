PYTHON ?= python3

includedir := doc/include
defaultsfile := $(includedir)/defaults.txt

datadir := data
mandir := $(datadir)/share/man/man1


doc: manpages

manpages: $(mandir)/logfilter.1.gz

$(defaultsfile): logfilter.py | $(includedir)
	$(PYTHON) \
		-c 'import logfilter; \
		    {print(f"{k} = {v}") for k,v in logfilter.DEFAULTS.items()}' \
		> $(defaultsfile)

$(includedir):
	mkdir $(includedir)

$(mandir)/logfilter.1.gz: doc/logfilter.1.rst $(defaultsfile) | $(mandir)
	rst2man --config=doc/docutils.conf $< \
		| gzip -9 > $@

$(mandir):
	mkdir -p $(mandir)

clean:
	rm -rf $(includedir) $(datadir)

lint: pylint mypy

pylint:
	pylint logfilter.py

mypy:
	mypy --strict logfilter.py

test:
	$(PYTHON) -m doctest logfilter.py
	$(PYTHON) test/test_logfilter.py

.PHONY: doc manpages clean lint pylint mypy test
