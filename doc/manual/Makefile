PDFLATEX = pdflatex
BIBTEX = bibtex
MAKEABBREV = ./makeabbrev

CP = cp -a



.PHONY : doc
doc : calunium-mag-manual raspi-mag-manual bgs-mag-manual

.PHONY : calunium-mag-manual
calunium-mag-manual : calunium-mag-images makeabbrev gitlog.tex
	$(PDFLATEX) -jobname calunium-mag-manual manual 
	$(MAKEABBREV) calunium-mag-manual
#	$(BIBTEX) calunium-mag-manual
	$(PDFLATEX) -jobname calunium-mag-manual manual 

.PHONY : raspi-mag-manual
raspi-mag-manual : raspi-mag-images makeabbrev gitlog.tex
	$(PDFLATEX) -jobname raspi-mag-manual manual
	$(MAKEABBREV) raspi-mag-manual
#	$(BIBTEX) raspi-mag-manual
	$(PDFLATEX) -jobname raspi-mag-manual manual

.PHONY : bgs-mag-manual
bgs-mag-manual : bgs-mag-images makeabbrev gitlog.tex
	$(PDFLATEX) -jobname bgs-mag-manual manual
	$(MAKEABBREV) bgs-mag-manual
#	$(BIBTEX) bgs-mag-manual
	$(PDFLATEX) -jobname bgs-mag-manual manual


.PHONY : clean
clean :
# .tpt: PDF thumbnails from thumbpdf
	$(RM) -- *.atfi *.aux *.bbl *.blg *.dvi *.lof *.log *.lot *.tpt *.toc */*.aux _region_.tex calunium-mag-manual.{abb,abr,atfi,aux,lof,log,out,toc,upa} raspi-mag-manual.{abb,abr,atfi,aux,lof,log,out,toc,upa} bgs-mag-manual.{abb,abr,atfi,aux,lof,log,out,toc,upa}

.PHONY : realclean
realclean : clean
	$(RM) calunium-mag-manual.pdf raspi-mag-manual.pdf bgs-mag-manual.pdf

.PHONY : calunium-mag-images
images : calunium-mag/images/FLC100_shield_v1_0_sch.pdf \
	calunium-mag/images/FLC100_shield_v2_0_sch.pdf \
	calunium-mag/images/Calunium_v2_1_sch.pdf \
	calunium-mag/images/system-overview.pdf

calunium-mag/images/FLC100_shield_v1_0_sch.pdf : ../../hardware/FLC100_shield/shield_v1.0/FLC100_shield_v1.0_sch.pdf
	$(CP) $< $@

calunium-mag/images/FLC100_shield_v2_0_sch.pdf : ../../hardware/FLC100_shield/shield_v2.0/FLC100_shield_v2.0_sch.pdf
	$(CP) $< $@

calunium-mag/images/Calunium_v2_1_sch.pdf : ../../hardware/Calunium/hardware/pcb/Calunium_v2.1/Calunium_v2.1_sch.pdf
	$(CP) $< $@

calunium-mag/images/system-overview.pdf : calunium-mag/images/src/system-overview.odg
	libreoffice --headless --convert-to pdf --outdir $(dir $@) $<


.PHONY : raspi-mag-images
raspi-mag-images : raspi-mag/images/system-overview.pdf

raspi-mag/images/system-overview.pdf : raspi-mag/images/src/system-overview.odg
	libreoffice --headless --convert-to pdf --outdir $(dir $@) $<

.PHONY :  bgs-mag-images
# images : raspi-mag/images/system-overview.pdf
images :


makeabbrev : makeabbrev.c

GIT_LOG_PATH = . \
../../hardware/FLC100_shield/shield_v1.0/FLC100_shield_v1.0_sch.pdf \
../../hardware/FLC100_shield/shield_v2.0/FLC100_shield_v2.0_sch.pdf \
../../hardware/Calunium/hardware/pcb/Calunium_v2.1/Calunium_v2.1_sch.pdf

.PHONY : gitlog.tex
gitlog.tex :
	TZ=UTC git log -1 --date=iso --format='\newcommand{\gitCommitDate}{%cd}%n\newcommand{\gitCommit}{%H}' $(GIT_LOG_PATH) > $@
	TZ=UTC git log -1 --date=iso --format='\newcommand{\gitCommitYear}{%cd}' . | sed 's/-[^}]*//' >> $@

