git clone --recursive https://github.com/stevemarple/AuroraWatchNet.git 
git clone --recursive https://github.com/stevemarple/auroraplot.git
git clone --recursive https://github.com/stevemarple/python-MCP342x.git
mkdir ~/bin
. ~/.bashrc
cd ~/bin
ln -s ../AuroraWatchNet/software/server/bin/raspimagd.py
ln -s ../AuroraWatchNet/software/server/bin/log_ip
ln -s ../AuroraWatchNet/software/server/bin/upload_data.py
cd ~
