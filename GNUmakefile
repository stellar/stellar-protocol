
MDFILES := README.md $(wildcard core/*.md ecosystem/*.md drafts/*.md)
HTMLFILES := $(MDFILES:.md=.html)

all: $(HTMLFILES)
clean:
	rm -f $(HTMLFILES) *~ */*~
.PHONY: all clean

%.html: %.md
	@case $$(pandoc --version | sed -ne '1s/pandoc *//p') in \
		[01].*) echo "Need pandoc version 2 or later" >&2; exit 1 ;; \
	esac
	title=$$(sed -ne '20q; s/^Title: *//p;' $^); \
	pagetitle=$${title:-$(notdir $*)}; \
	pandoc -s -f gfm -t html -V "pagetitle:$$pagetitle" -o $@ \
		-V "title:$$title" \
		-H "$$PWD/github-pandoc.css" $^
