#ifndef FDPAIR_HH
#define FDPAIR_HH

#include "../common/Common.hh"

#define INV_FD (-1)

class FdPair {

    public:

        #if USE_SSL
            FdPair(int fd0, int fd1, SSL *ssl): _fd0(fd0), _fd1(fd1), _ssl(ssl) {};
        #else
            FdPair(int fd0, int fd1): _fd0(fd0), _fd1(fd1) {};
        #endif

        ~FdPair() {}

        int get_fd0() {
            return _fd0;
        }

        int get_fd1() {
            return _fd1;
        }

        void set_fd0(int fd0) {
            _fd0 = fd0;
        }

        void set_fd1(int fd1) {
            _fd1 = fd1;
        }

        #if USE_SSL
            void setSSL(SSL* ssl) {
                _ssl = ssl;
            }

            SSL* getSSL() {
                return _ssl;
            }

            int tork_ssl_read(void *buf, int n)
            {
                int nread, error;
                std::unique_lock<std::mutex> res_lock(_ssl_mtx);
                nread = SSL_peek(_ssl, buf, n);
                error = SSL_get_error(_ssl, nread);
                if (nread < 0) {
                    switch (error) {
                        case SSL_ERROR_WANT_READ:
                        case SSL_ERROR_WANT_WRITE: return 0;
                        case SSL_ERROR_SYSCALL:
                            return (errno == EAGAIN || errno == EINTR) ? 0 : -1;
                        default: return -1;
                    }
                }
                return (nread == 0) ? -1 : SSL_read(_ssl, buf, n);
            }

            int tork_ssl_write(void *buf, int n)
            {
                int nwrite, error;
                std::unique_lock<std::mutex> res_lock(_ssl_mtx);
                nwrite = SSL_write(_ssl, buf, n);
                error = SSL_get_error(_ssl, nwrite);
                if (nwrite < 0) {
                    switch (error) {
                        case SSL_ERROR_WANT_READ:
                        case SSL_ERROR_WANT_WRITE: return 0;
                        case SSL_ERROR_SYSCALL:
                            return (errno == EAGAIN || errno == EINTR) ? 0 : -1;
                        default: return -1;
                    }
                }
                return (nwrite == 0) ? -1 : nwrite;
            }
        #endif

    private:

        int _fd0;
        int _fd1;

        #if USE_SSL
            SSL* _ssl;
            std::mutex _ssl_mtx;
        #endif
};

#endif //FDPAIR_HH
