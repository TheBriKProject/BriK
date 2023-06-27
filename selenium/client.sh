#!/bin/bash

if [ $USER != "tork" ]; then
    echo "You need to run this script as tork user."
    exit 1
fi

export DISPLAY=:1
Xvfb $DISPLAY -screen 0 1024x768x16 &
fluxbox &
x11vnc -display $DISPLAY -bg -forever -nopw -quiet -listen 0.0.0.0 -xkb

# Run direct experiment, without Tor
case $TOR_MODE in

    direct)
    python3 /home/tork/client.py --mode=2 --tor_channel=$TOR_CHANNEL
    ;;

    tor)
    python3 /home/tork/client.py --mode=1 --config_file=config_without_TorK.ini \
        --tor_channel=$TOR_CHANNEL
    ;;

    tork)
    # Run with TorK
    # ! K_min is defined automatically for testing
    python3 /home/tork/client.py --mode=0 --tor_channel=$TOR_CHANNEL \
        --max_chunks=$MAX_CHUNKS --chunk=$CHUNK_SIZE --ts_min=$TS_MIN \
        --ts_max=$TS_MAX --ch_active=$CH_ACTIVE --k_min=$K_MIN
    ;;
esac
