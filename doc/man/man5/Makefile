SRCDIR = ../../txt
SOURCES := $(SRCDIR)/clush.conf.txt \
           $(SRCDIR)/groups.conf.txt
OBJECTS  := $(SOURCES:$(SRCDIR)/%.txt=%.5)

%.5: ../../txt/%.txt
	rst2man $< $@

all: $(OBJECTS)

force: clean all

clean:
	@rm -v $(OBJECTS)
