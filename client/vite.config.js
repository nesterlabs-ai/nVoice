import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            // Proxy /connect to the backend server
            '/connect': {
                target: 'http://0.0.0.0:7860',
                changeOrigin: true,
            },
            // Proxy /graph/* endpoints to the backend server
            '/graph': {
                target: 'http://0.0.0.0:7860',
                changeOrigin: true,
            },
            // Proxy /a2ui/* endpoints to the backend server
            '/a2ui': {
                target: 'http://0.0.0.0:7860',
                changeOrigin: true,
            },
        },
    },
});
