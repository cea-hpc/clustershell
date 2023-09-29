SRCDIR = ../../txt
SOURCES := $(SRCDIR)/clubak.txt \
           $(SRCDIR)/cluset.txt \
           $(SRCDIR)/clush.txt \
           $(SRCDIR)/nodeset.txt
OBJECTS  := $(SOURCES:$(SRCDIR)/%.txt=%.1)

%.1: ../../txt/%.txt
	rst2man $< $@

all: $(OBJECTS)

force: clean all

clean:
	@rm -v $(OBJECTS)
