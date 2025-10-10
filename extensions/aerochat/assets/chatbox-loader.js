
  
// (function () {
//   // let storeUrl = 'aerochatuser1.myshopify.com';
//   let storeUrl = `${Shopify.shop}`;
//   // or hardcoded
//   // let storeUrl = "https://demostore-aerochat.myshopify.com";

//   console.log(storeUrl);


//   const endpoint = 'https://app.aerochat.ai/chat/api/v1/get-script-url';

//   fetch(endpoint, {
//     method: 'POST',
//     headers: {
//       'Content-Type': 'application/json',
//     },
//     body: JSON.stringify({ shop: storeUrl })
//   })
//     .then(response => response.json())
//     .then(data => {

//       if(data.url){
//         const scriptUrl = typeof data === 'string' ? data : data.url;
//         if (scriptUrl && !document.querySelector(`script[src="${scriptUrl}"]`)) {
//           const scriptTag = document.createElement('script');
//           scriptTag.src = scriptUrl;
//           scriptTag.async = true;
  
//           scriptTag.onload = function () {
//             console.log('Injected script loaded:', scriptUrl);
//           };
  
//           document.head.appendChild(scriptTag);
//         }
//       }
      
//     })
//     .catch(error => {
//       console.error('Error fetching script URL:', error);
//     });
// })();
(function () {
  const storeUrl = `${Shopify.shop}`;
  const endpoint = 'https://app.aerochat.ai/chat/api/v1/get-script-url';
  const CACHE_KEY = `aerochat_widget_${storeUrl}`;
  const CACHE_TTL = 7 * 24 * 60 * 60 * 1000; // 7 days

  console.log("Initializing AeroChat widget for:", storeUrl);

  function loadScript(scriptUrl) {
    if (!scriptUrl) return;
    if (document.querySelector(`script[src="${scriptUrl}"]`)) return; // already loaded

    const script = document.createElement('script');
    script.src = scriptUrl;
    script.async = true;
    script.onload = () => console.log('✅ AeroChat widget loaded:', scriptUrl);
    script.onerror = () => {
      console.warn('⚠️ Failed to load script, clearing cache.');
      localStorage.removeItem(CACHE_KEY);
    };
    document.head.appendChild(script);
  }

  // 🧠 Try cache first
  const cached = localStorage.getItem(CACHE_KEY);
  if (cached) {
    try {
      const data = JSON.parse(cached);
      const isExpired = Date.now() - data.timestamp > CACHE_TTL;
      if (!isExpired && data.url) {
        console.log('⚡ Loading widget from cache:', data.url);
        loadScript(data.url);
        return; // stop here, no need to call API
      } else {
        localStorage.removeItem(CACHE_KEY);
      }
    } catch {
      localStorage.removeItem(CACHE_KEY);
    }
  }

  // 🌐 If not cached or expired, call API
  fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ shop: storeUrl })
  })
    .then(res => res.json())
    .then(data => {
      const scriptUrl = data?.url;
      if (scriptUrl) {
        // 💾 Save in cache
        localStorage.setItem(
          CACHE_KEY,
          JSON.stringify({ url: scriptUrl, timestamp: Date.now() })
        );
        loadScript(scriptUrl);
      }
    })
    .catch(err => console.error('Error fetching AeroChat script URL:', err));
})();
