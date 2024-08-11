PDFLATEX = pdflatex
BIBTEX = bibtex
MAKEABBREV = ./makeabbrev

CP = cp -a

MANUALS = calunium-mag-manual raspi-mag-manual bgs-mag-manual riometer-manual

.PHONY : doc
.NOTPARALLEL : doc
doc : calunium-mag-manual raspi-mag-manual bgs-mag-manual riometer-manual

.PHONY : calunium-mag-manual
calunium-mag-manual : clean calunium-mag-images makeabbrev gitlog.tex
	$(RM) $@.pdf
	$(PDFLATEX) -jobname calunium-mag-manual manual
	$(MAKEABBREV) calunium-mag-manual
#	$(BIBTEX) calunium-mag-manual
	$(PDFLATEX) -jobname calunium-mag-manual manual
	$(PDFLATEX) -jobname calunium-mag-manual manual
	$(PDFLATEX) -jobname calunium-mag-manual manual

.PHONY : raspi-mag-manual
raspi-mag-manual : clean raspi-mag-images makeabbrev gitlog.tex
	$(RM) $@.pdf
	$(PDFLATEX) -jobname raspi-mag-manual manual
	$(MAKEABBREV) raspi-mag-manual
#	$(BIBTEX) raspi-mag-manual
	$(PDFLATEX) -jobname raspi-mag-manual manual
	$(PDFLATEX) -jobname raspi-mag-manual manual
	$(PDFLATEX) -jobname raspi-mag-manual manual

.PHONY : bgs-mag-manual
.NOTPARALLEL : bgs-mag-manual
bgs-mag-manual : clean bgs-mag-images makeabbrev gitlog.tex
	$(RM) $@.pdf
	$(PDFLATEX) -jobname bgs-mag-manual manual
	$(MAKEABBREV) bgs-mag-manual
#	$(BIBTEX) bgs-mag-manual
	$(PDFLATEX) -jobname bgs-mag-manual manual
	$(PDFLATEX) -jobname bgs-mag-manual manual
	$(PDFLATEX) -jobname bgs-mag-manual manual

.PHONY : riometer-manual
riometer-manual : clean riometer-images makeabbrev gitlog.tex
	$(RM) $@.pdf
	$(PDFLATEX) -jobname riometer-manual manual
	$(MAKEABBREV) riometer-manual
#	$(BIBTEX) riometer-manual
	$(PDFLATEX) -jobname riometer-manual manual
	$(PDFLATEX) -jobname riometer-manual manual
	$(PDFLATEX) -jobname riometer-manual manual


CLEAN_EXTS = abb abr atfi aux bbl blg dvi fdb_latexmk fls lof log lot out toc tpt upa
# CLEAN_DOT_EXTS = $(foreach ext,$(CLEAN_EXTS),.$(ext))

.PHONY : clean
clean :
# .tpt: PDF thumbnails from thumbpdf
	$(RM) -- *.atfi *.aux *.bbl *.blg *.dvi *.lof *.log *.lot *.tpt *.toc */*.aux $(foreach ext,$(CLEAN_EXTS),$(addsuffix .$(ext), manual $(MANUALS))) manual.pdf manual.synctex.gz

.PHONY : realclean
realclean : clean
	$(RM) calunium-mag-manual.pdf raspi-mag-manual.pdf bgs-mag-manual.pdf riometer-manual.pdf

.PHONY : calunium-mag-images
calunium-mag-images : calunium-mag/images/FLC100-shield-v1-0-sch.pdf \
	calunium-mag/images/FLC100-shield-v2-0-sch.pdf \
	calunium-mag/images/Calunium-v2-1-sch.pdf \
	calunium-mag/images/system-overview.pdf

calunium-mag/images/FLC100-shield-v1-0-sch.pdf : ../../hardware/FLC100_shield/shield_v1.0/FLC100_shield_v1.0_sch.pdf
	$(CP) $< $@

calunium-mag/images/FLC100-shield-v2-0-sch.pdf : ../../hardware/FLC100_shield/shield_v2.0/FLC100_shield_v2.0_sch.pdf
	$(CP) $< $@

calunium-mag/images/Calunium-v2-1-sch.pdf : ../../hardware/Calunium/hardware/pcb/Calunium_v2.1/Calunium_v2.1_sch.pdf
	$(CP) $< $@

calunium-mag/images/system-overview.pdf : calunium-mag/images/src/system-overview.odg
	libreoffice --headless --convert-to pdf --outdir $(dir $@) $<


.PHONY : raspi-mag-images
raspi-mag-images : raspi-mag/images/system-overview.pdf

raspi-mag/images/system-overview.pdf : raspi-mag/images/src/system-overview.odg
	libreoffice --headless --convert-to pdf --outdir $(dir $@) $<

.PHONY :  bgs-mag-images
# images : raspi-mag/images/system-overview.pdf
bgs-mag-images :


.PHONY :  riometer-images
# images : riometer/images/system-overview.pdf
riometer-images :

makeabbrev : makeabbrev.c

GIT_LOG_PATH = . \
../../hardware/FLC100_shield/shield_v1.0/FLC100_shield_v1.0_sch.pdf \
../../hardware/FLC100_shield/shield_v2.0/FLC100_shield_v2.0_sch.pdf \
../../hardware/Calunium/hardware/pcb/Calunium_v2.1/Calunium_v2.1_sch.pdf

.PHONY : gitlog.tex
gitlog.tex :
	TZ=UTC git log -1 --date=iso --format='\newcommand{\gitCommitDate}{%cd}%n\newcommand{\gitCommit}{%H}' $(GIT_LOG_PATH) > $@
	TZ=UTC git log -1 --date=iso --format='\newcommand{\gitCommitYear}{%cd}' . | sed 's/-[^}]*//' >> $@

