// Test Firestore response details
const fetch = globalThis.fetch;

(async () => {
  const projectId = 'store-ea555';
  const apiKey = 'AIzaSyC0dyLxc8R1SsO2SAURqUgTBWnq044_JPw';
  const collection = 'books';
  const endpoint = 'https://firestore.googleapis.com/v1/projects/' + projectId + '/databases/(default)/documents/' + collection + '?key=' + apiKey;
  
  console.log('Fetching:', endpoint);
  
  try {
    const response = await fetch(endpoint);
    console.log('Status:', response.status);
    
    const text = await response.text();
    console.log('Response Text:', text);
    
    try {
      const data = JSON.parse(text);
      console.log('\nParsed JSON:');
      console.log('  documents:', data.documents);
      console.log('  moreResults:', data.moreResults);
      if (data.documents) {
        console.log('  Count:', data.documents.length);
        data.documents.forEach((doc, i) => {
          console.log('\nDoc ' + i + ':', doc.name);
          console.log('  Fields:', JSON.stringify(doc.fields, null, 2).substring(0, 300));
        });
      }
    } catch (e) {
      console.log('\nNot valid JSON');
    }
  } catch (error) {
    console.error('Error:', error);
  }
})();