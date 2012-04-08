NAME=ClusterShell_UserGuide_EN
SOURCE=$(NAME).tex
PDF=$(SOURCE:.tex=.pdf)

all: $(SOURCE)
	@export CSVERSION=$$(PYTHONPATH=../../lib; python -c "from ClusterShell import __version__; print __version__;"); \
	export CSGITREV=$$(cd ../..; git rev-parse --short HEAD); \
	export HUMDATENOW=$$(date +%Y%m%d%H%M%S); \
	pdflatex "\newcommand{\version}{$$CSVERSION}\newcommand{\vertag}{CS-USERGUIDE-$$CSVERSION-$$CSGITREV-$$HUMDATENOW}\input{$(SOURCE)}" && mv $(PDF) $(NAME)_$$CSVERSION.pdf

test: $(SOURCE)
	evince $(SOURCE)

clean:
	rm -f *.aux *.log *.out *.synctex.gz* *.toc
