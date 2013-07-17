PDFLATEX = pdflatex
BIBTEX = bibtex

CP = cp -a
.PHONY : doc
doc : images
	$(PDFLATEX) manual
#	$(BIBTEX) installation-manual
	$(PDFLATEX) manual

.PHONY : clean
clean:
# .tpt: PDF thumbnails from thumbpdf
	$(RM) -- *.atfi *.aux *.bbl *.blg *.dvi *.lof *.log *.lot *.tpt *.toc */*.aux manual.out _region_.tex


.PHONY : images
images : images/Calunium_v2_1_sch.pdf

images/Calunium_v2_1_sch.pdf : ../../hardware/Calunium/hardware/pcb/Calunium_v2.1/Calunium_v2.1_sch.pdf
	$(CP) $< $@
