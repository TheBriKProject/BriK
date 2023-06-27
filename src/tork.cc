#include "common/Common.hh"
#include "common/cmdline.h"
#include "cli/CliUnixServer.hh"
#include "tordriver/TorPTClient.hh"
#include "tordriver/TorPTServer.hh"
#include "tordriver/TorController.hh"

#if USE_SSL
    #include  "common/SSL.hh"
#else
    #warning "USE_SSL is set to ZERO (0), SSL connection is disabled!"
#endif

#include "tordriver/SocksProxyClient.hh"
#include "tordriver/SocksProxyServer.hh"
#include "controller/ControllerClient.hh"
#include "controller/ControllerServer.hh"

#include <boost/format.hpp>

struct params
{
    std::string mode;
    std::string config;
    int port;
    unsigned int frag_len;
    unsigned int frag_int;
    std::string bridge_ssl_cert;
    std::string bridge_ssl_key;
    unsigned int chunk_size;
    unsigned int max_chunks;
    unsigned int ts_min;
    unsigned int ts_max;
    int k_min;
    bool ch_active;
    bool abort_on_conn;
    std::string bridge_ip;
    unsigned int cli_port;
    bool disable_circ_change;
    bool disable_dynamic_rate;
};


void terminate_handler(int signum)
{
    if (signum == SIGKILL) {
        std::cerr << "[TORK]: Received SIGKILL. Terminating ..." << std::endl;
        exit(EXIT_SUCCESS);

    } else if (signum == SIGTERM) {
        std::cerr << "[TORK]: Received SIGTERM. Terminating ..." << std::endl;
        exit(EXIT_SUCCESS);

    } else if (signum == 1) {
        std::cerr << "[TORK]: Tor closed stdin. Exiting ..." << std::endl;
    }

}

void terminate_cleanly(TrafficShaper *ts) {
    if (ts->terminate() == 0) {
        std::cerr << "[TORK]: Traffic Shaper terminated cleanly." << std::endl;
    }
}

void parse_args(int argc, char* argv[], params &p)
{
    cmdline::parser parser;
    parser.add<std::string>("mode", 'm', "TorK mode operation (client/bridge)", true, "client/bridge");
    parser.add<int>("port", 'p', "Port to use in services", true);
    parser.add<std::string>("bridge_ssl_cert", 's', "Bridge SSL certificate path", false, "../certs/bridge_cert.pem");
    parser.add<std::string>("bridge_ssl_key", 'x', "Bridge SSL private key path", false, "../certs/bridge_private.key");
    parser.add<unsigned int>("chunk", 'c', "Frame chunk size in bytes", false, 3125);
    parser.add<unsigned int>("max_chunks", 'C', "Max number of chunks that compose a frame", false, 1);
    parser.add<unsigned int>("ts_min", 'n', "Traffic Shaper minimum rating in microsseconds", false, 5000);
    parser.add<unsigned int>("ts_max", 'N', "Traffic Shaper maximum rating in microsseconds", false, 15000);
    parser.add<int>("k_min", 'k', "Min number of users in the same KCircuit (client mode only)", false, -1);
    parser.add<bool>("ch_active", 'a', "Request Tor channel to be active by default (client mode only)", false, false);
    parser.add<bool>("abort_on_conn", 'A', "Abort client when bridge connection fails (client mode only)", false, false);
    parser.add<std::string>("bridge_ip", 'B', "Bridge IP (chaff mode only)", false, "127.0.0.1");
    parser.add<unsigned int>("cli_port", 't', "Cli Port stats local port (client mode only)", false, 9091);
    parser.add<bool>("disable_circ_change", 'g', "Disable circuit CHANGE (bridge mode only)", false, false);
    parser.add<bool>("disable_dynamic_rate", 'r', "Disable dynamic TS rate (bridge mode only)", false, false);
    parser.parse_check(argc, argv);

    p.mode                 = parser.get<std::string>("mode");
    p.port                 = parser.get<int>("port");
    p.bridge_ssl_cert      = parser.get<std::string>("bridge_ssl_cert");
    p.bridge_ssl_key       = parser.get<std::string>("bridge_ssl_key");
    p.max_chunks           = parser.get<unsigned int>("max_chunks");
    p.chunk_size           = parser.get<unsigned int>("chunk");
    p.ts_min               = parser.get<unsigned int>("ts_min");
    p.ts_max               = parser.get<unsigned int>("ts_max");
    p.k_min                = parser.get<int>("k_min");
    p.ch_active            = parser.get<bool>("ch_active");
    p.abort_on_conn        = parser.get<bool>("abort_on_conn");
    p.bridge_ip            = parser.get<std::string>("bridge_ip");
    p.cli_port             = parser.get<unsigned int>("cli_port");
    p.disable_circ_change  = parser.get<bool>("disable_circ_change");
    p.disable_dynamic_rate = parser.get<bool>("disable_dynamic_rate");

    if (p.mode != "bridge" && p.mode != "client" && p.mode != "chaff") {
        std::cerr << "Invalid mode. Please select bridge, client or chaff" << std::endl;
        exit(0);
    }

    if (p.mode == "bridge") {
        std::ifstream ifile;
        ifile.open(p.bridge_ssl_cert);
        if(!ifile) {
            std::cerr << "Could not find bridge SSL certificate. Use the flag -s to specify a valid path." << std::endl;
            exit(0);
        }
        ifile.close();
        ifile.open(p.bridge_ssl_key);
        if(!ifile) {
            std::cerr << "Could not find bridge SSL private key. Use the flag -x to specify a valid path." << std::endl;
            exit(0);
        }
    }
}

int main(int argc, char* argv[])
{
    params p;

    std::signal(SIGINT, terminate_handler);
    std::signal(SIGTERM, terminate_handler);

    parse_args(argc, argv, p);

    #if USE_SSL
        SSL_load_error_strings();
        OpenSSL_add_all_algorithms();

        SSL_CTX* ctx;
    #endif

    const std::string TORK_WELCOME  = "[TORK]: Welcome to TorK! Version %s";
    const std::string TORK_MODE     = "[TORK]: Running in %s mode.";
    const std::string TORK_SETTINGS = "[TORK]: Using --max_chunk=%d --chunk_size=%d --ts_min=%d --ts_max=%d";

    if (p.mode == "chaff") { // Tor-less chaff mode
        std::cout << TORK_BANNER << std::endl;
        std::cout << (boost::format(TORK_WELCOME) % TORK_VERSION) << std::endl;
        std::cout << (boost::format(TORK_MODE)
                        % "Tor-less CHAFF") << std::endl;
        std::cout << (boost::format(TORK_SETTINGS)
                        % p.max_chunks % p.chunk_size % p.ts_min % p.ts_max)
                        << std::endl;
        std::cout << (boost::format("[TORK]: Using --bridge=%s -p=%d")
                        % p.bridge_ip % p.port) << std::endl;

        SocksProxyClient proxy;
        CliUnixServer cli_server(p.cli_port);
        TrafficShaper traffic_shaper;
        ControllerClient controller(p.max_chunks, p.chunk_size, p.ts_min,
                                    p.ts_max, p.k_min, false,
                                    p.abort_on_conn, nullptr, &proxy,
                                    nullptr, &cli_server,
                                    &traffic_shaper);

        //Direct Connect to the bridge IP
        unsigned char ip[4];
        sscanf(p.bridge_ip.c_str(), "%hhu.%hhu.%hhu.%hhu", &ip[0], &ip[1], &ip[2], &ip[3]);
        int fd_bridge = proxy.app_connect(0x01, (void *)ip, p.port);

        if (fd_bridge == INV_FD) {
            std::cerr << "Could not establish direct connection to the bridge!" << std::endl;
        } else {
            std::cerr << "Connected successfully to the bridge!" << std::endl;
        }

        #if USE_SSL
            ctx = init_client_ssl();
            proxy.initialize(&controller, true, fd_bridge, ctx, RUN_BACKGROUND);
        #else
            proxy.initialize(&controller, true, fd_bridge, RUN_BACKGROUND);
        #endif
        traffic_shaper.initialize(&controller, p.ts_max,
                                    TS_STRATEGY_CONSTANT, TS_STATE_ON,
                                    RUN_BACKGROUND);

        cli_server.initialize(&controller, RUN_FOREGROUND);

        #if USE_SSL
            SSL_CTX_free(ctx);
        #endif

        terminate_handler(1);
        terminate_cleanly(&traffic_shaper);
        return 0;
    }

    if (p.mode == "client") {
        TorPTClient pt;
        SocksProxyClient proxy;
        TorController tor_controller;
        CliUnixServer cli_server(p.cli_port);
        TrafficShaper traffic_shaper;
        ControllerClient controller(p.max_chunks, p.chunk_size, p.ts_min,
                                    p.ts_max, p.k_min, p.ch_active,
                                    p.abort_on_conn, &pt, &proxy,
                                    &tor_controller, &cli_server,
                                    &traffic_shaper);

        pt.log(NOTICE, TORK_BANNER);
        pt.log(NOTICE, str(boost::format(TORK_WELCOME) % TORK_VERSION));

        pt.log(NOTICE, str(boost::format(TORK_MODE) % "CLIENT"));
        pt.log(NOTICE, str(boost::format(TORK_SETTINGS)
                        % p.max_chunks % p.chunk_size % p.ts_min % p.ts_max));
        pt.log(NOTICE, str(boost::format("Client configured with --k_min=%d --ch_active=%d")
                        % p.k_min % p.ch_active));

        controller.config(p.port, 9061);

        pt.initialize(&controller, RUN_FOREGROUND);
        #if USE_SSL
            ctx = init_client_ssl();
            proxy.initialize(&controller, false, INV_FD, ctx, RUN_BACKGROUND);
        #else
            proxy.initialize(&controller, false, INV_FD, RUN_BACKGROUND);
        #endif
        tor_controller.initialize(&controller, RUN_BACKGROUND);
        traffic_shaper.initialize(&controller, p.ts_max,
                                    TS_STRATEGY_CONSTANT, TS_STATE_ON,
                                    RUN_BACKGROUND);

        if (pt.exitOnStdinClose()) {
            cli_server.initialize(&controller, RUN_BACKGROUND);

            //wait until tor signal us to close
            pt.waitUntilStdinClose();
        } else {
            cli_server.initialize(&controller, RUN_FOREGROUND);
        }

        #if USE_SSL
            SSL_CTX_free(ctx);
        #endif

        terminate_handler(1);
        terminate_cleanly(&traffic_shaper);
        return 0;
    }

    if (p.mode == "bridge") {

        TorPTServer pt;
        SocksProxyServer proxy;
        CliUnixServer cli_server(9095);
        TrafficShaper traffic_shaper;
        ControllerServer controller(p.max_chunks, p.chunk_size, p.ts_min,
                                    p.ts_max, &pt, &proxy, &cli_server,
                                    &traffic_shaper, p.disable_circ_change,
                                    p.disable_dynamic_rate);

        pt.log(NOTICE, TORK_BANNER);
        pt.log(NOTICE, str(boost::format(TORK_WELCOME) % TORK_VERSION));

        pt.log(NOTICE, str(boost::format(TORK_MODE) % "BRIDGE"));
        pt.log(NOTICE, str(boost::format(TORK_SETTINGS)
                        % p.max_chunks % p.chunk_size % p.ts_min % p.ts_max));

        pt.initialize(&controller, RUN_FOREGROUND);
        #if USE_SSL
            ctx = init_server_ssl();
            LoadSSLCertificate(ctx, p.bridge_ssl_cert.c_str(),
                               p.bridge_ssl_key.c_str());
            proxy.initialize(&controller, ctx, p.port,
                             std::stoi(pt.getOnionPort()), RUN_BACKGROUND);
        #else
            proxy.initialize(&controller, p.port,
                             std::stoi(pt.getOnionPort()), RUN_BACKGROUND);
        #endif
        traffic_shaper.initialize(&controller, p.ts_max,
                                    TS_STRATEGY_CONSTANT, TS_STATE_IDLE,
                                    RUN_BACKGROUND);

        if (pt.exitOnStdinClose()) {
            cli_server.initialize(&controller, RUN_BACKGROUND);

            //wait until tor signal us to close
            pt.waitUntilStdinClose();
        } else {
            cli_server.initialize(&controller, RUN_FOREGROUND);
        }


        #if USE_SSL
            SSL_CTX_free(ctx);
        #endif

        terminate_handler(1);
        terminate_cleanly(&traffic_shaper);
        return 0;
    }

    std::cerr << "Fatal: Unknown mode " << p.mode << std::endl;
    return 1;
}
