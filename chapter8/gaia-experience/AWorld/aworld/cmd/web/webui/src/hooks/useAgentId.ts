import { useEffect, useState } from 'react';

export const useAgentId = () => {
  const [agentId, setAgentId] = useState<string>('');

  // Get agent ID from URL parameters
  const getAgentIdFromURL = (): string => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('agentid') || '';
  };

  // Update agent ID in URL parameters
  const updateURLAgentId = (id: string) => {
    const url = new URL(window.location.href);
    if (id) {
      url.searchParams.set('agentid', id);
    } else {
      url.searchParams.delete('agentid');
    }
    window.history.replaceState({}, '', url.toString());
  };

  // Set new agent ID and update URL
  const setAgentIdAndUpdateURL = (id: string) => {
    setAgentId(id);
    updateURLAgentId(id);
  };

  useEffect(() => {
    // Check for agent ID in URL on initialization
    const urlAgentId = getAgentIdFromURL();
    
    if (urlAgentId) {
      // If there is an agent ID in the URL, use it
      setAgentId(urlAgentId);
    }
  }, []);

  return {
    agentId,
    setAgentIdAndUpdateURL,
    updateURLAgentId,
  };
}; 