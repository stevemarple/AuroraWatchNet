git clone --recursive https://github.com/stevemarple/AuroraWatchNet.git 
git clone --recursive https://github.com/stevemarple/auroraplot.git
git clone --recursive https://github.com/stevemarple/Calunium.git
git clone --recursive https://github.com/stevemarple/xboot.git
mkdir ~/bin
. ~/.bashrc
cd ~/bin
ln -s ../AuroraWatchNet/software/server/bin/awnetd.py
ln -s ../AuroraWatchNet/software/server/bin/send_cmd.py
ln -s ../AuroraWatchNet/software/server/bin/log_ip
ln -s ../AuroraWatchNet/software/server/bin/upload_data.py
cd ~
