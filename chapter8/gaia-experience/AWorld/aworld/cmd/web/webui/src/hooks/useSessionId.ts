import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

export const useSessionId = () => {
  const [sessionId, setSessionId] = useState<string>('');

  // Get session ID from URL parameters
  const getSessionIdFromURL = (): string => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('session_id') || '';
  };

  // Update session ID in URL parameters
  const updateURLSessionId = (id: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set('session_id', id);
    window.history.replaceState({}, '', url.toString());
  };

  // Generate new session ID and update URL
  const generateNewSessionId = (): string => {
    const newId = uuidv4();
    setSessionId(newId);
    updateURLSessionId(newId);
    console.log('generateNewSessionId', newId);
    return newId;
  };

  useEffect(() => {
    // Check URL for session ID on initialization
    const urlSessionId = getSessionIdFromURL();

    if (urlSessionId) {
      // If URL has session ID, use it
      setSessionId(urlSessionId);
    } else {
      // If URL does not have session ID, generate a new one
      generateNewSessionId();
    }
  }, []);

  return {
    sessionId,
    setSessionId,
    generateNewSessionId,
    updateURLSessionId,
  };
}; 