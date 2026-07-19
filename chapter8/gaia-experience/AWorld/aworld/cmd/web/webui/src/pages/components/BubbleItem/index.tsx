import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import CardDefault from './cardDefault';
import CardLinkList from './cardLinkList';
import './index.less';
import type { ToolCardData } from './utils';
import { extractToolCards } from './utils';

interface BubbleItemProps {
  sessionId: string;
  data: string;
  trace_id: string;
  onOpenWorkspace?: (data: ToolCardData) => void;
  isLoading?: boolean;
}

const BubbleItem: React.FC<BubbleItemProps> = ({ sessionId, data, onOpenWorkspace, isLoading = false }) => {
  // Used to record the last opened workspace data to avoid repeated calls
  const lastWorkspaceDataRef = useRef<ToolCardData | null>(null);

  // Modify the openWorkspace function to directly call the external callback
  const openWorkspace = (data: ToolCardData) => {
    if (onOpenWorkspace) {
      onOpenWorkspace(data);
    }
  };

  const { segments } = extractToolCards(data);

  // Compare whether two workspace data are the same
  const isWorkspaceDataEqual = (data1: ToolCardData | null, data2: ToolCardData | null): boolean => {
    if (!data1 && !data2) return true;
    if (!data1 || !data2) return false;

    // Compare key fields to determine if it is the same workspace
    return (
      data1.tool_call_id === data2.tool_call_id &&
      data1.artifacts?.length === data2.artifacts?.length &&
      JSON.stringify(data1.artifacts) === JSON.stringify(data2.artifacts)
    );
  };

  // Logic for automatically opening workspace - only during streaming output
  useEffect(() => {
    // Only automatically open workspace during streaming output
    if (!isLoading) {
      return;
    }

    // Find the latest tool_card with workspace functionality (without distinguishing card type)
    const toolCardSegments = segments.filter(segment => segment.type === 'tool_card');

    // Search from the last one to find the first tool_card with artifacts
    const latestWorkspaceCard = toolCardSegments
      .slice()
      .reverse()
      .find(segment => {
        return segment.type === 'tool_card' &&
          segment.data?.artifacts?.length > 0;
      });

    if (latestWorkspaceCard && latestWorkspaceCard.type === 'tool_card' && onOpenWorkspace) {
      const currentWorkspaceData = latestWorkspaceCard.data;

      // Check if the current workspace data is the same as the last one
      if (!isWorkspaceDataEqual(lastWorkspaceDataRef.current, currentWorkspaceData)) {
        // Update the recorded workspace data
        lastWorkspaceDataRef.current = currentWorkspaceData;

        // Use requestAnimationFrame to ensure opening workspace after the next frame render
        const frameId = requestAnimationFrame(() => {
          openWorkspace(currentWorkspaceData);
        });

        return () => cancelAnimationFrame(frameId);
      } else {
        console.log("latest workspace opened!", currentWorkspaceData, lastWorkspaceDataRef.current)
      }
    }
  }, [segments, onOpenWorkspace, openWorkspace, isLoading]);

  // console.log('segments:', segments);
  return (
    <div className="card">
      {segments.map((segment, index) => {
        if (segment.type === 'text') {
          return (
            <div className="markdownbox" key={`text-${index}`}>
              <ReactMarkdown>{segment.content}</ReactMarkdown>
            </div>
          );
        } else if (segment.type === 'tool_card') {
          const cardType = segment.data?.card_type;
          if (cardType === 'tool_call_card_link_list') {
            return <CardLinkList key={`tool-${index}`} sessionId={sessionId} data={segment.data} onOpenWorkspace={openWorkspace} />;
          } else {
            return <CardDefault key={`tool-${index}`} sessionId={sessionId} data={segment.data} onOpenWorkspace={openWorkspace} />;
          }
        }
      })}
      {/* Remove the internal Drawer */}
    </div>
  );
};

export default BubbleItem;
