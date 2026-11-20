// Test Firestore with API key parameter
import fetch from 'node-fetch';

// Config from .env
const projectId = 'store-ea555';
const apiKey = 'AIzaSyC0dyLxc8R1SsO2SAURqUgTBWnq044_JPw';
const collection = 'books';

// Test 1: With key parameter
async function test1() {
  console.log('=== Test 1: With key parameter ===');
  const endpoint = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/${collection}?key=${apiKey}`;
  console.log('Endpoint:', endpoint);
  
  try {
    const response = await fetch(endpoint);
    console.log('Status:', response.status);
    console.log('Status Text:', response.statusText);
    const text = await response.text();
    console.log('Response:', text.substring(0, 300));
  } catch (err) {
    console.error('Error:', err.message);
  }
}

// Test 2: Without key parameter (current code behavior)
async function test2() {
  console.log('\n=== Test 2: Without key parameter ===');
  const endpoint = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/${collection}`;
  console.log('Endpoint:', endpoint);
  
  try {
    const response = await fetch(endpoint);
    console.log('Status:', response.status);
    console.log('Status Text:', response.statusText);
    const text = await response.text();
    console.log('Response:', text.substring(0, 300));
  } catch (err) {
    console.error('Error:', err.message);
  }
}

test1();
test2();