# +-----------------------------------------------+
# | TorK Development - Docker image configuration  |
# +-----------------------------------------------+
FROM ubuntu:jammy
RUN apt update && apt upgrade -y && apt install -y build-essential gcc g++ gdb
RUN apt install -y git libssl-dev tcpdump dnsutils curl tmux netcat-openbsd
RUN apt install -y libboost-all-dev sudo

# Install latest cmake
RUN apt install -y apt-transport-https ca-certificates gnupg software-properties-common wget
RUN wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc 2>/dev/null | gpg --dearmor - | tee /etc/apt/trusted.gpg.d/kitware.gpg >/dev/null
RUN apt-add-repository 'deb https://apt.kitware.com/ubuntu/ jammy main'
RUN apt install -y cmake

#Install Tor from source
RUN apt install -y autotools-dev automake libevent-dev
RUN git clone https://git.torproject.org/tor.git /usr/src/tor
WORKDIR /usr/src/tor
RUN git checkout tags/tor-0.4.7.13
RUN sed -i "s/entry_guards_note_guard_failure(guard->in_selection, guard);/\/\/entry_guards_note_guard_failure(guard->in_selection, guard);/g" /usr/src/tor/src/feature/client/entrynodes.c
RUN sh autogen.sh
RUN ./configure --disable-asciidoc
RUN make
RUN make install

RUN useradd -m runner
RUN HOME=/home/runner sudo -u runner mkdir /home/runner/actions-runner
RUN HOME=/home/runner sudo -u runner curl -o /home/runner/actions-runner/actions-runner-linux-x64-2.294.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.294.0/actions-runner-linux-x64-2.294.0.tar.gz
RUN HOME=/home/runner sudo -u runner echo "a19a09f4eda5716e5d48ba86b6b78fc014880c5619b9dba4a059eaf65e131780  /home/runner/actions-runner/actions-runner-linux-x64-2.294.0.tar.gz" | shasum -a 256 -c
RUN HOME=/home/runner sudo -u runner tar xzf /home/runner/actions-runner/actions-runner-linux-x64-2.294.0.tar.gz -C /home/runner/actions-runner/

RUN apt update && apt install -y libtool libevent-dev python3 python3-dev python3-setuptools python3-pip
RUN DEBIAN_FRONTEND=noninteractive apt install -y sshpass libasound2 \
    libasound2-plugins alsa-utils alsa-oss pulseaudio pulseaudio-utils xvfb \
    dbus-x11 x11vnc fluxbox sudo nethogs vlc tshark httping

RUN pip3 install --upgrade pip
COPY selenium/requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt
# Dependency of requests
RUN pip3 install pysocks

RUN mkdir ~/tor

RUN useradd -m tork
RUN mkdir /home/tork/tor
RUN chown -R tork:tork /home/tork/tor
COPY selenium/client.sh /home/tork/client.sh
RUN chown tork:tork /home/tork/client.sh

COPY selenium/*.py /home/tork/
RUN chown tork:tork /home/tork/*.py
COPY selenium/config.ini /home/tork/config.ini
RUN chown tork:tork /home/tork/config.ini
COPY selenium/proxychains4.conf /etc/proxychains4.conf
COPY selenium/proxychains4.conf /etc/proxychains4_tor.conf

RUN sed -i "s/socks5.*$/socks5 127.0.0.1 9050/g" /etc/proxychains4_tor.conf
