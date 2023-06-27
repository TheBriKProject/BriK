New variant of the Tor system which aims at increasing its resilience against traffic correlation attacks by introducing K-anonymous circuits

## Documentation

The complete documentation is available under the `docs` folder.

## Releases and Version Information

The `main` branch should be considered as the latest `beta` version. This
indicates that the version is reasonably stable but lacks exhaustive testing.

Features branches should be considered as `unstable` as they contain fresh
new features and experimental patches which were not thoroughly tested.

**Latest Stable Version:** 2.0.9.1

**Current Stable Branch:** 2.0.x

For exhaustive testing, only stable versions should be used.

**Branch 1.x:** Branch `1.x` already reached it's end-of-life, thus it will not
receive any new features, patches or security fixes.

## Docker Compose build
1. Make sure you have Docker installed.

1. Start by simply building the images:
```bash
docker-compose build
```

1. Start the deployment. This will start one bridge and 3 clients each of them configured with a K_min of 3.
```bash
docker-compose up
```

Wait until all three clients are ready. Wait until they bootstrapped completely.
<details>
  <summary>Example of output</summary>

```
...
tork-client-1   | Oct 21 15:54:28.000 [notice] new bridge descriptor 'Unnamed' (fresh): $DE4FC808272C68486CB10787D0725FA5F21AD192~Unnamed [0B3TYMp1eTHDtVnYZiFKlOcSU2Mr0SNW9wBBzibRd0s] at 172.24.0.2
tork-client-1   | Oct 21 15:54:28.000 [notice] Bootstrapped 75% (enough_dirinfo): Loaded enough directory info to build circuits
tork-client-1   | Oct 21 15:54:28.000 [notice] Bootstrapped 90% (ap_handshake_done): Handshake finished with a relay to build circuits
tork-client-1   | Oct 21 15:54:28.000 [notice] Bootstrapped 95% (circuit_create): Establishing a Tor circuit
tork-client-1   | Oct 21 15:54:29.000 [notice] Bootstrapped 100% (done): Done
tork-client-2   | Oct 21 15:54:29.000 [notice] Bootstrapped 100% (done): Done
tork-client-3   | Oct 21 15:54:29.000 [notice] Bootstrapped 100% (done): Done
```
</details>

1. You can get the ephemeral SOCKS ports for all three clients by running:
```bash
docker ps --no-trunc
```

You should see an output identical to the following:
```
CONTAINER ID                                                       IMAGE         COMMAND                                                                                                        CREATED         STATUS                    PORTS                                                                       NAMES
974936c516d9411768ab7d1262f8e419e348da4f68a83ecb494c3aa5f8df5c0d   tork:latest   "sh -c 'tor -f /usr/src/tork/tor_confs/torrc_docker_client_clean bridge \"tork $(dig bridge +short):8081\"'"   7 minutes ago   Up 27 seconds (healthy)   0.0.0.0:52946->9051/tcp, 0.0.0.0:52944->9061/tcp, 0.0.0.0:52945->9091/tcp   tork-client-3
2afc3ab3aa8e5b1fbf1e1821f600b8ac04d72b0ccec5f23d2595dd6b32eb0883   tork:latest   "sh -c 'tor -f /usr/src/tork/tor_confs/torrc_docker_client_clean bridge \"tork $(dig bridge +short):8081\"'"   7 minutes ago   Up 27 seconds (healthy)   0.0.0.0:52947->9051/tcp, 0.0.0.0:52948->9061/tcp, 0.0.0.0:52949->9091/tcp   tork-client-1
a8b77cbf02f772976ab982f9f9a067baa403d76b5ebdb7a02ff44d0870149227   tork:latest   "sh -c 'tor -f /usr/src/tork/tor_confs/torrc_docker_client_clean bridge \"tork $(dig bridge +short):8081\"'"   7 minutes ago   Up 26 seconds (healthy)   0.0.0.0:52950->9051/tcp, 0.0.0.0:52951->9061/tcp, 0.0.0.0:52952->9091/tcp   tork-client-2
2391e38dbc6dfcbb9f41e5967e86716ef128d988358dc6dd12e1b8ffea5cf4c5   tork:latest   "sh -c 'tor -f /usr/src/tork/tor_confs/torrc_docker_bridge_clean'"                                             7 minutes ago   Up 37 seconds (healthy)   0.0.0.0:8081->8081/tcp, 0.0.0.0:8085->9095/tcp                              tork-bridge-1
```

1. Take note on the SOCKS ports of all three denoted as `0.0.0.0:PORT->9051/tcp`.

1. You can know test each client by curling `ifconfig.io`, a page that displays the user IP address.
```bash
curl -x socks5h://127.0.0.1:52946 ifconfig.io
185.220.101.30

curl -x socks5h://127.0.0.1:52947 ifconfig.io
45.83.104.137

curl -x socks5h://127.0.0.1:52950 ifconfig.io
212.95.50.77
```

## Manual Build

You can also build BriK without Docker by installing the following dependencies:

Dependencies:
*   CMake version 3.10+
*   gcc (g++) 7.5.0+
*   Lib OpenSSL (Dev) 1.1.1+
*   Libboost C++ 1.65.0+
*   Tor 0.4.1.9+

Developed and tested under Ubuntu bionic 18.04.5 LTS (4.15.0-112-generic).

To build from the source:
```
cmake .
make
```

To disable SSL:

Edit the `src/common/Common.hh` and set the `USE_SSL` to zero:

```
...
#define USE_SSL  (1)
...
```

SSL disable causes a compilation warning and it should be use for debugging purposes.

### Requirements
Disable bridge / guard mark as down by comment the line:

```
src/feature/client/entrynodes.c in entry_guard_failed():

entry_guards_note_guard_failure(guard->in_selection, guard);
```

Patch:
```diff
diff --git a/src/feature/client/entrynodes.c b/src/feature/client/entrynodes.c
index e7324487da..d540d5cc62 100644
--- a/src/feature/client/entrynodes.c
+++ b/src/feature/client/entrynodes.c
@@ -2574,7 +2574,7 @@ entry_guard_failed(circuit_guard_state_t **guard_state_p)
   if (! guard || BUG(guard->in_selection == NULL))
     return;

-  entry_guards_note_guard_failure(guard->in_selection, guard);
+  //entry_guards_note_guard_failure(guard->in_selection, guard);

   (*guard_state_p)->state = GUARD_CIRC_STATE_DEAD;
   (*guard_state_p)->state_set_at = approx_time();
```

### Using Docker (without Docker Compose)
To quickly deploy a TorK developing setup, use both images of Docker:
*   `tork:regular` -> contains the TorK and all its dependencies
*   `tork:sgx`     -> contains the TorK, its dependencies and support for SCONE,
an extension to Intel SGX in order to provide additional security.

**Tip**: This images can be generated using the `Docker` and `DockerSGX` folders
available on the `tork-analysis` repo. The building process can take some time,
specially for the `tork:sgx` image. You will need to be able to access the
`sconecuratedimages/crosscompilers` private docker image, by requesting
access through email (See SCONE Refs at bottom).

You will need to setup a Docker network:
```
docker network create torknet
docker network ls
docker network inspect torknet
```

**Attention:** Depending on the IP subnet used by Docker you may need to
change `/usr/src/tork/tor_confs/torrc_docker_client_clean` configuration file
to successfully connect TorK clients to the bridge.

To run a TorK Bridge container simply run:
```
docker run --rm --hostname=bridge --name=bridge --network=torknet -it tork:regular tor -f /usr/src/tork/tor_confs/torrc_docker_bridge_clean
```

To run a TorK Client container under the same network run:
```
docker run --rm --hostname=client1 --name=client1 --network=torknet -p 9051:9051 -p 9091:9091 -it tork:regular tor -f /usr/src/tork/tor_confs/torrc_docker_client_clean
```
*   9091 will be the control port, where TorK clients can send commands via CLI interface.
*   9051 will be the Tor SOCKS port, where clients can configure their browser to send
request through Tor.

Access the CLI interface by using the forward port on the host, set a KCircuit of N, (in this case 1),
and activate the channel:
```
nc 127.0.0.1 9091
set_k 1
ch active
```

A few seconds later, Tor should give a indication of 100% Bootstrap complete, thus
we can send request to the Tor Network:
```
curl -x socks5h://127.0.0.1:9051 https://ifconfig.io
```

The output should be the IP address of the exit node used by Tor.

To cleanly exit the client, use the command `shut` on the cli interface.

#### Using Intel SGX Support
To run TorK under Intel SGX support use the `tork:sgx` image.
Only TorK will be running inside SGX enclave, and then, the executable of Tor
must be provided mounted on the container.

First, make sure you are using a compatible Intel CPU and the Linux SGX Driver
is installed:

*   [List of compatible CPU](https://ark.intel.com/content/www/us/en/ark/search/featurefilter.html?productType=873&2_SoftwareGuardExtensions=Yes%20with%20Intel%C2%AE%20ME)
*   [Installation of SGX Driver](https://sconedocs.github.io/sgxinstall/)

You can test if TorK is able to run in `Hardware Mode` by running the following command:

```
docker run --rm --privileged $MOUNT_SGXDEVICE -e SCONE_VERSION=1 -e SCONE_MODE=HW -it tork:sgx ./tork
```

You should obtain an output like this when you are able to run TorK inside an enclave (confirm that `SCONE_MODE=hw`):
```
export SCONE_QUEUES=4
export SCONE_SLOTS=256
export SCONE_SIGPIPE=0
export SCONE_MMAP32BIT=0
export SCONE_SSPINS=100
export SCONE_SSLEEP=4000
export SCONE_LOG=3
export SCONE_HEAP=67108864
export SCONE_STACK=2097152
export SCONE_CONFIG=/etc/sgx-musl.conf
export SCONE_ESPINS=10000
export SCONE_MODE=hw
export SCONE_ALLOW_DLOPEN=no
export SCONE_MPROTECT=no
musl version: 1.1.24
Revision: f4655f36e58c3f91fd4e085285c3a163a841e802 (Thu Apr 30 11:19:42 2020 +0000)
Branch: HEAD

Enclave hash: 92e69d133e2adb1de7f7cc4b0e96d1f01a272faed4cc7543cb7a476808105573
[TORK] Welcome to Tork!
usage: ./tork --mode=string --port=int [options] ...
options:
  -m, --mode               TorK mode operation (client/bridge) (string)
  -p, --port               Port to use in services (int)
  -s, --bridge_ssl_cert    Bridge SSL certificate path (string [=../certs/bridge_cert.pem])
  -x, --bridge_ssl_key     Bridge SSL private key path (string [=../certs/bridge_private.key])
  -?, --help               print this message
```

If you receive the following output:
```
[SCONE|ERROR] ./tools/starter-exec.c:1231:main(): Could not create enclave: Error opening SGX device
```
Make sure that the SGX drivers are properly installed and the container can access the sgx device (usually under `/dev/sgx/`).

##### Running TorK

Use the following commands to launch a bridge
and client with support for SGX enclaves:

```
docker run --rm --privileged --hostname=bridge --name=bridge --network=torknet $MOUNT_SGXDEVICE -v ~/tor/src/app/tor:/usr/local/bin/tor -it tork:sgx tor -f /usr/src/tork/tor_confs/torrc_docker_bridge_clean
```

```
docker run --rm --privileged --hostname=client1 --name=client1 --network=torknet $MOUNT_SGXDEVICE -v ~/tor/src/app/tor:/usr/local/bin/tor -p 9051:9051 -p 9091:9091 -it tork:sgx tor -f /usr/src/tork/tor_confs/torrc_docker_client_clean
```

### Using Vagrant
To deploy a TorK developing setup using vagrant, locate the `machine_setup`
under the `tork-analysis` git repo and run the following commands to deploy
one TorK bridge and two TorK clients:

```
vagrant up tork_bridge tork_client1 tork_client2
```

After a few minutes, the VMs will be ready. Just SSH into them and locate TorK
folder under the ´/home/vagrant/SharedFolder/`.

```
vagrant ssh tork_bridge
cd ~/SharedFolder/tork
tor -f tor_confs/torrc_bridge_clean
```

```
vagrant ssh tork_client1
cd ~/SharedFolder/tork
tor -f tor_confs/torrc_client_clean
```

The process of accessing and controlling the CLI is the same, as in Docker.
