NAME=ClusterShell_UserGuide_EN
SOURCE=$(NAME).tex
PDF=$(SOURCE:.tex=.pdf)

all: $(SOURCE)
	@export CSVERSION=$$(PYTHONPATH=../../lib; python -c "from ClusterShell import __version__; print __version__;"); \
	export CSGITREV=$$(cd ../..; git rev-parse --short HEAD); \
	export HUMDATENOW=$$(date +%Y%m%d%H%M%S); \
	pdflatex "\newcommand{\version}{$$CSVERSION}\newcommand{\vertag}{CS-USERGUIDE-$$CSVERSION-$$CSGITREV-$$HUMDATENOW}\input{$(SOURCE)}" && mv $(PDF) $(NAME)_$$CSVERSION.pdf

test: all
	@export CSVERSION=$$(PYTHONPATH=../../lib; python -c "from ClusterShell import __version__; print __version__;"); \
	evince $(NAME)_$$CSVERSION.pdf

clean:
	rm -f *.aux *.log *.out *.synctex.gz* *.toc
