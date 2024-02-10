# OS config required
Enable SPI interface on raspi-config!!!

# OS lib required
python3
pip
python3-venv

# Raspberry as spotify connect device
https://dtcooper.github.io/raspotify/

# Env & Dependencies
On project directory:
python3.9 -m venv env
source env/bin/activate
pip install -r requirements.txt

# Environment file
Copy .env.template to .env and add required params

# run
On project directory:
```
source env/bin/activate
python rfid_media_player.py 
```

# Systemctl service
sudo cp rfid_media_player.service /usr/lib/systemd/system/
