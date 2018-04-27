FROM python:3.6
WORKDIR /app
ADD requirements.txt /app/requirements.txt
RUN wget "http://ftp.us.debian.org/debian/pool/main/o/opus/libopus0_1.2.1-1_amd64.deb" && dpkg -i "libopus0_1.2.1-1_amd64.deb"
RUN apt-get update && apt-get install ffmpeg -y
RUN pip install -r requirements.txt
COPY . /app
CMD python3 -m djbot