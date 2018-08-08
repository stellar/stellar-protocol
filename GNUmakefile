
MDFILES := README.md $(wildcard core/*.md ecosystem/*.md drafts/*.md)
HTMLFILES := $(MDFILES:.md=.html)

all: $(HTMLFILES)
clean:
	rm -f $(HTMLFILES) *~ */*~
.PHONY: all clean

%.html: %.md
	title=$$(sed -ne '20q; s/^Title: *//p;' $^); \
	pagetitle=$${title:-$(notdir $*)}; \
	pandoc -s -f gfm -t html -V "pagetitle:$$pagetitle" -o $@ \
		-V "title:$$title" \
		-H "$$PWD/github-pandoc.css" $^
