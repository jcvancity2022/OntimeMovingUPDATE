/*
 * OnTime Moving — where the Flask API lives.
 *
 * GitHub Pages only serves static files, so booking, availability and chat
 * need the Python server (server.py) running somewhere. Once it's hosted
 * (Render, Railway, PythonAnywhere, a VPS…), paste its URL below and every
 * page will use it. Until then the live site falls back to phone / email.
 */
window.ONTIME_API_BASE = (function () {
  var PRODUCTION_API = '';   // e.g. 'https://ontime-api.onrender.com/api'

  var host = location.hostname;
  if (location.protocol === 'file:') return 'http://localhost:5000/api';
  if (host === 'localhost' || host === '127.0.0.1') {
    // Served by Flask itself → same origin; otherwise (VS Code Live Server etc.) → Flask on :5000
    return location.port === '5000' ? '/api' : 'http://localhost:5000/api';
  }
  return PRODUCTION_API || null;   // null = no backend reachable from this host
})();
