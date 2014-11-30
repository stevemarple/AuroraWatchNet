PDFLATEX = pdflatex
BIBTEX = bibtex
MAKEABBREV = ./makeabbrev

CP = cp -a
.PHONY : doc
doc : images makeabbrev gitlog.tex
	$(PDFLATEX) manual
	$(MAKEABBREV) manual
#	$(BIBTEX) installation-manual
	$(PDFLATEX) manual

.PHONY : clean
clean:
# .tpt: PDF thumbnails from thumbpdf
	$(RM) -- *.atfi *.aux *.bbl *.blg *.dvi *.lof *.log *.lot *.tpt *.toc */*.aux manual.out manual.upa manual.abb manual.abr _region_.tex


.PHONY : images
images : images/FLC100_shield_v1_0_sch.pdf \
	images/FLC100_shield_v2_0_sch.pdf \
	images/Calunium_v2_1_sch.pdf \
	images/system-overview.pdf

images/FLC100_shield_v1_0_sch.pdf : ../../hardware/FLC100_shield/shield_v1.0/FLC100_shield_v1.0_sch.pdf
	$(CP) $< $@

images/FLC100_shield_v2_0_sch.pdf : ../../hardware/FLC100_shield/shield_v2.0/FLC100_shield_v2.0_sch.pdf
	$(CP) $< $@

images/Calunium_v2_1_sch.pdf : ../../hardware/Calunium/hardware/pcb/Calunium_v2.1/Calunium_v2.1_sch.pdf
	$(CP) $< $@

images/system-overview.pdf : images/src/system-overview.odg
	libreoffice --headless --draw --convert-to pdf --outdir images images/src/system-overview.odg

makeabbrev : makeabbrev.c

GIT_LOG_PATH = . \
../../hardware/FLC100_shield/shield_v1.0/FLC100_shield_v1.0_sch.pdf \
../../hardware/FLC100_shield/shield_v2.0/FLC100_shield_v2.0_sch.pdf \
../../hardware/Calunium/hardware/pcb/Calunium_v2.1/Calunium_v2.1_sch.pdf

.PHONY : gitlog.tex
gitlog.tex :
	git log -1 --date=iso --format='\newcommand{\gitCommitDate}{%cd}%n\newcommand{\gitCommit}{%H}' $(GIT_LOG_PATH) > $@
	git log -1 --date=iso --format='\newcommand{\gitCommitYear}{%cd}' . | sed 's/-[^}]*//' >> $@

