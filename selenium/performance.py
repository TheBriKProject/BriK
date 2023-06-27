"""Performance experiment module
"""
import os
import subprocess
import socket
import time
import stem.process
import requests

def save_to_file(filename, content):
    """Save results output to file.

    Args:
        filename (str): path to the file.
        content (str OR list): String or list of items to store to file.
    """
    print(f"Saving file {filename} ...")
    file = open(f"/results/{filename}", "w", encoding="utf8")
    if isinstance(content, list):
        for element in content:
            file.write(f"{element}\n")
    else:
        file.write(content)
    file.close()
    print(f"Done Saving file {filename}")

def wait_for_service(port):
    """Wait for a local port to become available.

    Args:
        port (int): Local port to wait for

    Returns:
        _type_: True if the service is running, False if all attempts to wait
            for the service failed.
    """
    #Wait until the port is available, we make sure the connection was
    #established
    attempts = 30
    while attempts >= 0:
        try:
            service_port = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            service_port.settimeout(15)
            service_port.connect(("127.0.0.1", port))
            break
        except (socket.timeout, ConnectionRefusedError) as exception:
            service_port.close()
            print(exception, "attempts:", attempts)
            attempts -= 1
            time.sleep(1)

    if attempts < 0:
        return False, None
    return True, service_port

class TimeoutException(Exception):
    """Generic TimeoutException

    Args:
        Exception (_type_):
    """

class Performance:
    """Performance Experiment Class
    """
    def __init__(self, client_settings, bridge_ip, mode, tor_channel, k_min):
        """
        Initializes Performance experiment
        """
        self.client_id = client_settings[0]
        self.socks = int(client_settings[1]["socksport"])
        self.control = int(client_settings[1]["controlport"])
        self.devnull = open(os.devnull, "w", encoding="utf8")
        self.torrc_dict = client_settings[1]
        self.bridge_ip = bridge_ip
        self.ssh_cmd_bridge_prefix = "ssh -t " + self.bridge_ip
        self.tor_binary_path = "/usr/local/bin/tor"
        self.results = "/results/"
        self.iperf_hostname = os.getenv("TARGET_HOST_IP")
        self.iperf_port = os.getenv("TARGET_HOST_PORT")
        self.host1 = os.getenv("HOST_1")
        self.host2 = os.getenv("HOST_2")
        self.tork_analysis_path = os.getenv("TORK_ANALYSIS_PATH")
        self.latency_site = "https://146.193.41.153/"
        self.mode = mode
        self.tor_channel = tor_channel
        self.k_min = k_min

        self.tunnelport = self.socks
        self.tor_ch = None
        self.tor = None
        self.nethogs = {}
        self.vlc_server = None
        self.iperf = None
        self.vlc_client = None
        self.tcpdump = {}

        self.iperf_server = None
        self.httping = None
        self.telemetry = {}

    def launch_tor_channel(self):
        """Launches a Tor Channel over SSH port forwarding

        Raises:
            Exception: TimeoutExpired
            Exception: Exception
        """
        print("Launching Tor channel")
        self.tunnelport = self.socks + 8
        cmd = f"ssh -D {self.tunnelport} root@127.0.0.1 -p 9101 -o".split(" ") \
                + ["ProxyCommand=ssh -W %h:%p torkhost.tor"]
        self.tor_ch = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
        try:
            out, err = self.tor_ch.communicate(timeout=15)
            print("[tor_ch PROCESS TERMINATED!]")
            print("[tor_ch stdout]: ", out.decode("utf-8"))
            print("[tor_ch stderr]: ", err.decode("utf-8"))
            raise Exception("SSH terminated in channel over Tor")
        except subprocess.TimeoutExpired:
            print("[tor_ch timeout]: Process didn't terminate, so it's good.")

        #Wait until the port is available, we make sure the connection was
        #established
        attempts = 30
        while attempts >= 0:
            try:
                tor_port = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tor_port.settimeout(15)
                tor_port.connect(("127.0.0.1", self.tunnelport))
                break
            except (socket.timeout, ConnectionRefusedError) as exception:
                print(exception, "attempts:", attempts)
                attempts -= 1
                time.sleep(1)
            finally:
                tor_port.close()

        if attempts < 0:
            raise Exception("Waited too long for the channel over Tor")

    def launch_tor(self):
        """Launch a Tor process as a subprocess of this module.
        """
        # launch tor process
        print(f"Tor config: {self.torrc_dict}")
        self.tor = stem.process.launch_tor_with_config(
                    config=self.torrc_dict,
                    tor_cmd=self.tor_binary_path,
                    init_msg_handler=print,
                    timeout=270)

    def launch_nethogs(self, resolution, location, cmd="nethogs -t", iteration=1):
        """Opens nethogs as a subprocess to gather network usage information.

        Args:
            stdout_file (str): Path to the file to save the nethogs output.
        """
        stdout_f = open(f"{self.results}/nethogs_{location}_{resolution}_{iteration}.txt",
                        "w", encoding="utf8")
        self.nethogs[location] = subprocess.Popen(cmd.split(" "),
                            stdout=stdout_f,
                            stderr=stdout_f)

    def launch_tcpdump_capture(self, resolution, location,
                                cmd="tcpdump -i eth1", output="", iteration=1,
                                temp=False):
        """Launches a remote tcpdump capture.

        """
        stdout_f = open(f"{self.results}/tcpdump_{location}_{resolution}_{iteration}.log",
                        "w", encoding="utf8")
        if temp:
            pcap_f = "temp.pcap"
        else:
            pcap_f = f"{output}pcap_{location}_{resolution}_{iteration}.pcap"

        self.tcpdump[location] = subprocess.Popen(f"{cmd} -w {pcap_f}".split(" "),
                                                    stdout=stdout_f,
                                                    stderr=stdout_f)

    def latency_test(self):
        """Launches a latency test agains a given site. The latency is measure
        by measuring the time it takes to get the header of the page.

        Returns:
            (str, str): HTTP status code, Elapsed time in seconds
        """
        proxies = {
            "http": "socks5://127.0.0.1:" + str(self.tunnelport),
            "https": "socks5://127.0.0.1:" + str(self.tunnelport)
        }
        response = requests.head(self.latency_site, proxies=proxies,
                                 allow_redirects=True, timeout=10)
        if response.status_code == 200:
            return str(response.status_code), str(response.elapsed)
        return str(response.status_code), "-"

    def kill_tor(self):
        """Kills the Tor opened locally on a subprocess
        """
        print("Killing Tor")
        self.tor.kill()

    def kill_tor_channel(self):
        """Kills the Tor channel over SSH port forwarding.
        """
        print("Killing Tor channel")
        self.tor_ch.kill()

    def kill_nethogs(self, location):
        """Kills the locally nethogs instance.
        """
        print("Killing Nethogs")
        if location not in self.nethogs:
            raise ValueError("Invalid location argument.")
        self.nethogs[location].kill()

    def kill_tcpdump(self, location):
        """Kills a tcpdump instance.
        """
        if location not in self.tcpdump:
            raise ValueError("Invalid location argument.")
        self.tcpdump[location].kill()

    def kill_vlc_server(self, vlc_server):
        """Kills vlc server on remote host.

        Args:
            vlc_server (str): hostname where the VLC server is currently running.
        """
        print("Killing vlc server on remote host")
        self.vlc_server.kill()
        cmd = f"ssh vlc@{vlc_server} -t pkill Xvfb"
        self.vlc_server = subprocess.Popen(cmd.split(" "), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

    def start_iperf(self, iteration):
        """Runs a local iperf instance against a server.

        Returns:
            str: iperf output results
        """
        cmd = f"proxychains4 -f /etc/proxychains4.conf iperf3 -c {self.iperf_hostname} -p {self.iperf_port} -t 30 -O 1 -f k -R"

        stdout_f = open(f"{self.results}/iperf_k_{self.k_min}_{iteration}.txt",
                        "w", encoding="utf8")

        self.iperf = subprocess.Popen(cmd.split(" "), stdout=stdout_f,
                            stderr=stdout_f)

    def kill_iperf(self):
        """Kills the iperf client.
        """
        self.iperf.kill()

    def run_vlc_server(self, vlc_server, video_sample, resolution, port="80",
                       iteration=1):
        """Launch a VLC server process on a remote host

        Args:
            vlc_server (str): remote hostname where to launch VLC server.
            video_sample (str): sample to be used in server.
            resolution (str): One of three possible resolutions (480p, 720p, 1080p)
            port (str, optional): Port where the server will listen for client
            requests. Defaults to "80". WARNING! Avoid picking random ports as
            Tor relays may reject traffic outside of a list of ports. Pick ports
            that relays usually don't block like 80 or 443.

        Raises:
            Exception: _description_
        """
        vlc_server_stdout_f = open(f"/results/vlc_server_{resolution}_stdout.log",
                                    "w", encoding="utf8")
        vlc_server_stderr_f = open(f"/results/vlc_server_{resolution}_stderr.log",
                                    "w", encoding="utf8")
        cmd = f"ssh vlc@{vlc_server} -t " + f"xvfb-run cvlc {video_sample} \
            --verbose=1" + " --sout '#http{mux=ffmpeg{mux=flv},dst=:" + port + \
            "/},dst=gather:std' --sout-all --sout-keep"
        self.vlc_server = subprocess.Popen(cmd.split(" "),
                                stdout=vlc_server_stdout_f,
                                stderr=vlc_server_stderr_f)
        print("Started vlc server on remote host")
        attempts = 30
        while attempts >= 0:
            try:
                vlc_port = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                vlc_port.settimeout(15)
                vlc_port.connect((vlc_server, int(port)))
                break
            except (socket.timeout, ConnectionRefusedError) as exception:
                vlc_port.close()
                print(exception, "attempts:", attempts)
                attempts -= 1
                time.sleep(1)

        if attempts < 0:
            self.kill_vlc_server(vlc_server)
            raise Exception("Waited too long for the vlc server")
        print("vlc server is ready")

    def _start_vlc_stream(self, vlc_server, remote_port, resolution):
        """Starts the stream towards the VLC server.

        Raises:
            Exception: _description_
        """
        if self.tor_channel == 1:
            proxychains_cmd = "proxychains4 -f /etc/proxychains4.conf "
        elif self.tor_channel == 0:
            proxychains_cmd = "proxychains4 -f /etc/proxychains4_tor.conf "
        if self.mode == 2:
            proxychains_cmd = ""
        # vlc will be resolved to the server once it reached the head_proxy
        cmd = f"{proxychains_cmd}cvlc -I rc --rc-host 127.0.0.1:9191 --verbose=1 \
            http://{vlc_server}:{remote_port}/"
        vlc_client_stdout_f = open(f"/results/vlc_client_{resolution}_stdout.log",
                                    "w", encoding="utf8")
        vlc_client_stderr_f = open(f"/results/vlc_client_{resolution}_stderr.log",
                                    "w", encoding="utf8")

        self.vlc_client = subprocess.Popen(cmd.split(" "),
                                                stdout=vlc_client_stdout_f,
                                                stderr=vlc_client_stderr_f)

        running, vlc_client_port = wait_for_service(9191)
        if not running:
            self.vlc_client.kill()
            raise Exception("Waited too long for the vlc rc interface")
        return vlc_client_port

    def run_vlc_client(self, stream_options, experiment_time=60):
        """Run a VLC client locally, by open a stream to the VLC server.

        Args:
            vlc_server (str): remote hostname where the VLC server is located.
            remote_port (str): remote port where the VLC server is listening for clients.
            resolution (str): One of three possible resolutions (480p, 720p, 1080p)
            experiment_time (int, optional): Streaming time experiment.
                Defaults to 60.

        Raises:
            Exception: _description_

        Returns:
            _type_: _description_
        """

        vlc_client_port = self._start_vlc_stream(stream_options[0],
                                                 stream_options[1],
                                                 stream_options[2])

        buff_size = 2048

        tork_insights = {"frames_displayed": [],
                         "frames_lost": [],
                         "data_bytes_received": [],
                         "data_bytes_sent": [],
                         "tor_bytes_received": [],
                         "tor_bytes_sent": [],
                         "other_bytes_received": [],
                         "other_bytes_sent": []}

        # If running in TorK mode, also connect to the stats endpoint to gather
        # the amount of received and sent data and chaff traffic
        if self.mode == 0:
            stats_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            stats_s.settimeout(15)
            stats_s.connect(("127.0.0.1", 9091))

        # Clean vlc welcome message and prompt
        part = ""
        while not part or ">" not in part:
            part = vlc_client_port.recv(buff_size).decode()

        for _ in range(0, experiment_time):
            if self.mode == 0:
                stats_s.send("stats_bytes\n".encode())
                stats_part = stats_s.recv(buff_size).decode()
                stats_part.rstrip('\n')
                stats_splitted = stats_part.split('\t')
                tork_insights["data_bytes_received"].append(int(stats_splitted[1]))
                tork_insights["data_bytes_sent"].append(int(stats_splitted[2]))
                tork_insights["tor_bytes_received"].append(int(stats_splitted[3]))
                tork_insights["tor_bytes_sent"].append(int(stats_splitted[4]))
                tork_insights["other_bytes_received"].append(int(stats_splitted[5]))
                tork_insights["other_bytes_sent"].append(int(stats_splitted[6]))

            #gather FPS info in time seconds of streaming
            vlc_client_port.send("stats\n".encode())
            stats = ""
            while True:
                part = vlc_client_port.recv(buff_size).decode()
                stats += part
                if not part or ">" in part:
                    # either 0 or end of data
                    break

            print("STATS: ", stats)
            for line in stats.split("\n"):
                if "frames displayed" in line:
                    tork_insights["frames_displayed"].append(int(line.split(":")[1]))
                elif "frames lost" in line:
                    tork_insights["frames_lost"].append(int(line.split(":")[1]))

            time.sleep(1)

        self.vlc_client.kill()

        return tork_insights["frames_displayed"],    \
               tork_insights["frames_lost"],         \
               tork_insights["data_bytes_received"], \
               tork_insights["data_bytes_sent"],     \
               tork_insights["tor_bytes_received"],  \
               tork_insights["tor_bytes_sent"],      \
               tork_insights["other_bytes_received"],\
               tork_insights["other_bytes_sent"]

    def streaming(self, vlc_hostname, vlc_port, video_sample_prefix,
                  video_resolutions=("480p", "720p", "1080p")):
        """Starts a streaming experiment, by launching a VLC server on a remote
        host, a VLC client locally and also all the necessary tools to gather
        information.

        Args:
            vlc_hostname (str): VLC server hostname which the client should connect.
            vlc_port (str): VLC server port where the server listen for clients.
            video_sample_prefix (str): Video sample prefix name
            video_resolutions (tuple, optional): Video sample resolution.
                Defaults to ("480p", "720p", "1080p").
        """
        for resolution in video_resolutions:
            # Abort if result files are about to be overwritten!
            if os.path.exists(f"/results/frames_displayed_{resolution}.txt"):
                raise Exception(f"!! Failsafe crash! Results of {resolution} exist!")
            print(f"Running Streaming {resolution} @ http://{vlc_hostname}:{vlc_port}/")
            self.launch_tcpdump_capture(resolution, "bridge", cmd="ssh root@bridge -t tcpdump -i any", output="/root/experiment/")
            self.launch_tcpdump_capture(resolution, "server", cmd=f"ssh vlc@{vlc_hostname} -t tcpdump", output="")
            self.launch_tcpdump_capture(resolution, "client", cmd="tcpdump", output=f"{self.results}/")
            self.run_vlc_server(vlc_hostname,
                            f"{video_sample_prefix}_{resolution}.mp4", resolution)
            self.launch_nethogs(resolution, "bridge",
                                cmd="ssh root@bridge -t /usr/sbin/nethogs -t")
            self.launch_nethogs(resolution, "server",
                                cmd=f"ssh vlc@{vlc_hostname} -t /usr/sbin/nethogs -t")
            self.launch_nethogs(resolution,"client", cmd="/usr/sbin/nethogs -t")
            frames_displayed, frames_lost, data_bytes_received,  \
            data_bytes_sent, tor_bytes_received, tor_bytes_sent, \
                other_bytes_received, other_bytes_sent =         \
                    self.run_vlc_client((vlc_hostname, vlc_port, resolution), 75)
            print(frames_displayed, frames_lost)
            # FPS
            save_to_file(f"frames_displayed_{resolution}.txt", frames_displayed)
            save_to_file(f"frames_lost_{resolution}.txt", frames_lost)

            # TorK data usage
            save_to_file(f"data_bytes_received_{resolution}.txt", data_bytes_received)
            save_to_file(f"data_bytes_sent_{resolution}.txt", data_bytes_sent)
            save_to_file(f"tor_bytes_received_{resolution}.txt", tor_bytes_received)
            save_to_file(f"tor_bytes_sent_{resolution}.txt", tor_bytes_sent)
            save_to_file(f"other_bytes_received_{resolution}.txt", other_bytes_received)
            save_to_file(f"other_bytes_sent_{resolution}.txt", other_bytes_sent)

            self.kill_tcpdump("bridge")
            self.kill_tcpdump("server")
            self.kill_tcpdump("client")

            self.kill_nethogs("bridge")
            self.kill_nethogs("server")
            self.kill_nethogs("client")
            self.kill_vlc_server(vlc_hostname)
            # Wait so the binded ports are released
            time.sleep(3)

    def start_telemetry(self, location, iteration, cmd="/home/tork/telemetry.sh"):
        """Starts a CPU and memory telemetry on a location

        Args:
            location (_type_): Prefix where the collection takes place
            iteration (_type_): Current iteration index
            cmd (str, optional): Defaults to "/home/tork/telemetry.sh".
        """
        stdout_f = open(f"{self.results}/telemetry_{location}_k_{self.k_min}_{iteration}.txt",
                        "w", encoding="utf8")

        self.telemetry[location] = subprocess.Popen(cmd.split(" "),
                            stdout=stdout_f,
                            stderr=stdout_f)

    def stop_telemetry(self, location):
        """Stops the CPU and memory telemtry on a location.

        Args:
            location (_type_): Prefix where the collection takes place
        """
        self.telemetry[location].kill()

    def extract_io_usage(self, pcap, output):
        """Extracts aggregated bandwidth usage from a pcap into output.

        Args:
            pcap (_type_): Path to the pcap file
            output (_type_): Path to the output file
        """
        stdout_f = open(f"{output}", "w", encoding="utf8")
        cmd = f"tshark -r {pcap} -q -Y tcp.srcport==8081&&tcp.len>0 -z io,stat,1,tcp.srcport==8081&&tcp.len>0"

        self.io_extract = subprocess.Popen(cmd.split(" "),
                    stdout=stdout_f,
                    stderr=stdout_f)

        try:
            self.io_extract.wait(timeout=120)
        except subprocess.TimeoutExpired as _:
            self.io_extract.kill()
            print("IO tooked too much time. Killed.")

    def launch_iperf_server(self, cmd):
        """Launches a iperf3 server

        Args:
            cmd (_type_): Full iperf command
        """
        stdout_f = open(f"{self.results}/iperf_server_k_{self.k_min}.txt",
                        "w", encoding="utf8")

        self.iperf_server = subprocess.Popen(cmd.split(" "),
                            stdout=stdout_f,
                            stderr=stdout_f)

    def kill_iperf_server(self):
        """Kills the iperf server.
        """
        self.iperf_server.kill()

    def launch_httping(self, iteration):
        """Launches a httping instance

        Args:
            iteration (_type_): Current iteration index
        """
        cmd = f"httping -c 10 -x 127.0.0.1:{self.socks} -5 -i 1 -r -S -l -g {self.latency_site}"

        stdout_f = open(f"{self.results}/httping_k_{self.k_min}_{iteration}.txt",
                        "w", encoding="utf8")

        self.httping = subprocess.Popen(cmd.split(" "),
                            stdout=stdout_f,
                            stderr=stdout_f)

        try:
            self.httping.wait(timeout=60)
        except subprocess.TimeoutExpired as _:
            print("Httping tooked to much time. Killed.")
            return False
        return True

    def collect_tork_insights(self, interval=60):
        """Connects to TorK's CLI port and fetch bytes statistics

        Args:
            interval (int, optional): Experiment time in seconds. Defaults to 60.

        Returns:
            _type_: _description_
        """
        buff_size = 2048

        tork_insights = {"data_bytes_received": [],
                         "data_bytes_sent": [],
                         "tor_bytes_received": [],
                         "tor_bytes_sent": [],
                         "other_bytes_received": [],
                         "other_bytes_sent": []}

        # If running in TorK mode, also connect to the stats endpoint to gather
        # the amount of received and sent data and chaff traffic
        if self.mode == 0:
            stats_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            stats_s.settimeout(15)
            stats_s.connect(("127.0.0.1", 9091))

        for _ in range(0, interval):
            if self.mode == 0:
                stats_s.send("stats_bytes\n".encode())
                stats_part = stats_s.recv(buff_size).decode()
                stats_part.rstrip('\n')
                stats_splitted = stats_part.split('\t')
                tork_insights["data_bytes_received"].append(int(stats_splitted[1]))
                tork_insights["data_bytes_sent"].append(int(stats_splitted[2]))
                tork_insights["tor_bytes_received"].append(int(stats_splitted[3]))
                tork_insights["tor_bytes_sent"].append(int(stats_splitted[4]))
                tork_insights["other_bytes_received"].append(int(stats_splitted[5]))
                tork_insights["other_bytes_sent"].append(int(stats_splitted[6]))
            time.sleep(1)

        return tork_insights["data_bytes_received"], \
               tork_insights["data_bytes_sent"],     \
               tork_insights["tor_bytes_received"],  \
               tork_insights["tor_bytes_sent"],      \
               tork_insights["other_bytes_received"],\
               tork_insights["other_bytes_sent"]

    def throughput(self, iteration, proxy_hostname):
        """Placeholder for the throughput and latency experiment

        Args:
            iteration (_type_): Current iteration index.
            proxy_hostname (_type_): IP or fqdn of the proxy hostname (when
            hosted outside Docker swarm setup)
        """
        if self.mode != 2:
            self.launch_nethogs(self.k_min, "bridge",
                                cmd="ssh root@bridge -t /usr/sbin/nethogs -t -v 2",
                                iteration=iteration)
        #self.launch_nethogs(self.k_min, "server",
        #                    cmd=f"ssh vlc@{proxy_hostname} -t /usr/sbin/nethogs -t -v 2",
        #                    iteration=iteration)
        self.start_telemetry("host_1", iteration, cmd=f"ssh vagrant@{self.host1} -t {self.tork_analysis_path}/machine_setup/Performance/telemetry.sh")
        self.start_telemetry("host_2", iteration, cmd=f"ssh vagrant@{self.host2} -t {self.tork_analysis_path}/machine_setup/Performance/telemetry.sh")
        self.launch_nethogs(self.k_min,"client", cmd="/usr/sbin/nethogs -t -v 2",
                            iteration=iteration)
        # Store temporary pcap
        self.launch_tcpdump_capture(self.k_min, "client",
            cmd="tcpdump -i any", output=f"{self.results}/",
            iteration=iteration, temp=True)

        print(f"K: {self.k_min}\t[# {iteration}] Started iperf...")
        self.start_iperf(iteration)

        data_bytes_received,  \
        data_bytes_sent, tor_bytes_received, tor_bytes_sent, \
        other_bytes_received, other_bytes_sent =         \
            self.collect_tork_insights(interval=40)

        try:
            try:
                self.iperf.wait(timeout=60)
            except subprocess.TimeoutExpired as _:
                self.kill_iperf()
                print("Iperf harshly terminated")
                return False

            print(f"K: {self.k_min}\t[# {iteration}] Iperf and insights finished.")

            # TorK data usage
            save_to_file(f"data_bytes_received_{self.k_min}_{iteration}.txt", data_bytes_received)
            save_to_file(f"data_bytes_sent_{self.k_min}_{iteration}.txt", data_bytes_sent)
            save_to_file(f"tor_bytes_received_{self.k_min}_{iteration}.txt", tor_bytes_received)
            save_to_file(f"tor_bytes_sent_{self.k_min}_{iteration}.txt", tor_bytes_sent)
            save_to_file(f"other_bytes_received_{self.k_min}_{iteration}.txt", other_bytes_received)
            save_to_file(f"other_bytes_sent_{self.k_min}_{iteration}.txt", other_bytes_sent)

            # Wait until iperf and insights are over to collect the latency
            print(f"K: {self.k_min}\t[# {iteration}] Running httping...")
            if self.launch_httping(iteration) is False:
                return False
            print(f"K: {self.k_min}\t[# {iteration}] Finished")

        finally:
            self.kill_tcpdump("client")

            if self.mode != 2:
                self.kill_nethogs("bridge")
            #self.kill_nethogs("server")
            self.kill_nethogs("client")
            self.stop_telemetry("host_1")
            self.stop_telemetry("host_2")

            # Extract network usage from temporary pcap
            print(f"K: {self.k_min}\t[# {iteration}] Extracting I/O usage...")
            self.extract_io_usage("temp.pcap",
                                f"{self.results}/io_client_k_{self.k_min}_{iteration}.txt")
            print(f"K: {self.k_min}\t[# {iteration}] Iteration finished!")

            # Wait so the binded ports are released
            time.sleep(3)

        return True

    def run(self, iterations=10):
        """Generic Performance experiment

        Args:
            iterations (int, optional): Number of repetions. Defaults to 10.
        """

        if self.mode != 2:
            self.launch_tor()
        if self.tor_channel == 1:
            self.launch_tor_channel()

        #if "client_data" not in os.getenv("TASK_NAME") and self.client_id == 1:
        #    for iteration in range(1, iterations + 1):
        #        self.throughput(iteration, target_hostname)
        #else:
        while True:
            print(f"{self.client_id} Starting download of dummy file ...")
            try:
                r = requests.get("http://146.193.41.153/tork/file_1", allow_redirects=True, proxies=dict(http=f"socks5h://127.0.0.1:{self.socks}",
                    https=f"socks5h://127.0.0.1:{self.socks}"))
            except Exception as ex:
                print("Exception: ", str(ex))
            print("Download finished")

        #if os.getenv("RUN_STREAMING", "0") == "1":
        #    for iteration in range(1, iterations + 1):
        #        self.streaming(target_hostname, target_port, "switzerland",
        #                        video_resolutions=("480p", "720p", "1080p",))

        if self.tor_channel == 1:
            self.kill_tor_channel()
        if self.mode != 2:
            self.kill_tor()
