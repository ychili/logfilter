PYTHON ?= python3

includedir := doc/include
helpfile := $(includedir)/help.txt
defaultsfile := $(includedir)/defaults.txt

doctxts: $(helpfile) $(defaultsfile)

$(helpfile): logfilter.py | $(includedir)
	COLUMNS=80 $(PYTHON) \
		-c 'import logfilter; \
		    logfilter.build_cla_parser(logfilter.DEFAULTS).print_help()' \
		> $(helpfile)

$(defaultsfile): logfilter.py | $(includedir)
	$(PYTHON) \
		-c 'import logfilter; \
		    {print(f"{k} = {v}") for k,v in logfilter.DEFAULTS.items()}' \
		> $(defaultsfile)

$(includedir):
	mkdir $(includedir)

clean:
	rm -rf $(includedir)

test:
	$(PYTHON) -m doctest logfilter.py
	$(PYTHON) test/test_logfilter.py

.PHONY: clean test
