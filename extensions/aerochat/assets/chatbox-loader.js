// document.addEventListener('DOMContentLoaded', function() {
//     const apiUrl = 'https://aerochat-staging.dummywebdemo.xyz/chat/get-script-url';  // Replace with your actual API URL
//     const shop = Shopify.shop;  // e.g., 'example.myshopify.com'
//     const color = '#ed4a69';  // Default; can pull from block settings if needed
  
//     fetch(apiUrl, {
//       method: 'POST',
//       headers: {
//         'Content-Type': 'application/json',
//       },
//       body: JSON.stringify({ shop: shop })  // Pass shop domain to your API
//     })
//     .then(response => {
//       if (!response.ok) {
//         throw new Error('API request failed: ' + response.status);
//       }
//       return response.json();
//     })
//     .then(data => {
//       const scriptUrl = data.url;
//       if (!scriptUrl) {
//         console.error('No script URL returned from API');
//         return;
//       }
  
//       // Dynamically create and append the script tag
//       const script = document.createElement('script');
//       script.src = scriptUrl;
//       script.async = true;
//       script.onload = () => console.log('Aerochat script loaded successfully');
//       script.onerror = () => console.error('Failed to load Aerochat script');
//       document.body.appendChild(script);
//     })
//     .catch(error => {
//       console.error('Error fetching Aerochat script URL:', error);
//     });
//   });
  
(function () {
  let storeUrl = 'aerochatuser1.myshopify.com';
  //let storeUrl = `https:\\${Shopify.shop}`;
  //let storeUrl = "demostore-aerochat.myshopify.com";

  console.log(storeUrl);

  const endpoint = 'https://app.aerochat.ai/chat/api/v1/get-script-url';

  fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ shop: storeUrl })
  })
    .then(response => response.json())
    .then(data => {

      if(data.url){
        const scriptUrl = typeof data === 'string' ? data : data.url;
        if (scriptUrl && !document.querySelector(`script[src="${scriptUrl}"]`)) {
          const scriptTag = document.createElement('script');
          scriptTag.src = scriptUrl;
          scriptTag.async = true;
  
          scriptTag.onload = function () {
            console.log('Injected script loaded:', scriptUrl);
          };
  
          document.head.appendChild(scriptTag);
        }
      }
      
    })
    .catch(error => {
      console.error('Error fetching script URL:', error);
    });
})();
