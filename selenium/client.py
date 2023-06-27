#!/bin/python3
"""Performance Client Script
"""
import configparser
import os
import socket
import subprocess
from argparse import ArgumentParser
from performance import Performance
from tbselenium.utils import start_xvfb, stop_xvfb

def get_dict_subconfig(config, section, prefix):
    """Return options in config for options with a `prefix` keyword."""
    return {option.split()[1]: config.get(section, option)
            for option in config.options(section) if option.startswith(prefix)}

def main():
    """Loads the performance experiment configuration and validates the values
    """
    parser = ArgumentParser()
    parser.add_argument("--clientid", type=int, default=os.getenv("TASK_SLOT"))
    parser.add_argument("--config_file", type=str, default="/home/tork/config.ini")
    parser.add_argument("--config", type=str, default="default")
    parser.add_argument("--virtual_display", type=str, default="720x1280")
    # Mode:
    # 0 -> TorK
    # 1 -> Tor vanilla
    # 2 -> Direct (Without Tor)
    parser.add_argument("--mode", type=int, default=0)
    parser.add_argument("--tor_channel", type=int, default=1)
    parser.add_argument("--max_chunks", type=int, default=1)
    parser.add_argument("--chunk", type=int, default=3125)
    parser.add_argument("--ts_min", type=int, default=1667)
    parser.add_argument("--ts_max", type=int, default=5001)
    parser.add_argument("--k_min", type=int, default=3)
    parser.add_argument("--ch_active", type=int, default=1)
    args = parser.parse_args()

    print("ARGS: ", args)

    #ffprefs = get_dict_subconfig(config, args.config, "ffpref")
    # Setup stem headless display
    xvfb_h = int(args.virtual_display.split('x')[0])
    xvfb_w = int(args.virtual_display.split('x')[1])
    xvfb_display = start_xvfb(xvfb_w, xvfb_h)

    while True:
        if args.mode == 1:
            bridge_ip = socket.gethostbyname("bridge")
            config = configparser.RawConfigParser()
            config.read(args.config_file)
            torrc_config = get_dict_subconfig(config, args.config, "torrc")
            torrc_config["bridge"] = f"{bridge_ip}:9090"

            # Get last k_min value from saved settings
            if os.path.isfile("/results/settings.txt"):
                with open("/results/settings.txt") as settings:
                    k_min, state = settings.readline().split(",")

                    k_min = int(k_min)

                    if state == "COMPLETED":
                        if k_min + 1 <= 25:
                            k_min, state = (k_min + 1, "NOT_PROCESSED")
                        else:
                            print("K_min is already at maximum value!")
                            return 0
            else:
                k_min, state = (1, "NOT_PROCESSED")

            # Save current settings
            with open("/results/settings.txt", "w") as settings:
                settings.write(f"{k_min},{state}")

            host1 = os.getenv("HOST_1")
            stdout_f = open(f"/results/docker_tor_k_{k_min}.log",
                            "w", encoding="utf8")
            cmd = f"ssh vagrant@{host1} -t \
                docker service scale tork_tor_client=" + str(k_min - 1)

            tor_setup = subprocess.Popen(cmd.split(" "),
                                stdout=stdout_f,
                                stderr=stdout_f)

            try:
                tor_setup.wait(timeout=60)
            except subprocess.TimeoutExpired as exp:
                raise ValueError("Scaling services took too long") from exp

        elif args.mode == 0:
            bridge_ip = socket.gethostbyname("bridge")
            config = configparser.RawConfigParser()
            config.read(args.config_file)
            torrc_config = get_dict_subconfig(config, args.config, "torrc")
            torrc_config["bridge"] = f"tork {bridge_ip}:8081"

            torrc_config["ClientTransportPlugin"] = f"tork exec \
                {os.getenv('TORK_BIN_PATH')} -m client -p 1088 -A 1 \
                --max_chunks {args.max_chunks} --chunk {args.chunk} \
                --ts_min {args.ts_min} --ts_max {args.ts_max} \
                --k_min {args.k_min} --ch_active {args.ch_active}"

        elif args.mode == 2:
            bridge_ip = ""
            torrc_config = {"socksport": "0", "controlport": "0"}
            k_min = 0
        else:
            raise ValueError("Invalid mode.")

        print("Starting experiment")

        performance = Performance((args.clientid, torrc_config), bridge_ip,
                                args.mode, args.tor_channel, args.k_min)
        performance.run(iterations=10)

if __name__ == '__main__':
    main()
