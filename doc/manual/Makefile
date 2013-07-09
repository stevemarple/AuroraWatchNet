PDFLATEX = pdflatex
BIBTEX = bibtex

.PHONY : doc
doc :
	$(PDFLATEX) manual
#	$(BIBTEX) installation-manual
	$(PDFLATEX) manual

.PHONY : clean
clean:
# .tpt: PDF thumbnails from thumbpdf
	$(RM) -- *.atfi *.aux *.bbl *.blg *.dvi *.lof *.log *.lot *.tpt *.toc */*.aux manual.out _region_.tex


