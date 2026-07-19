import type { Node, Edge } from '@xyflow/react';

//  Flowchart state type
type FlowState = {
  nodes: Node[];
  edges: Edge[];
};

//  Operation history stack
let historyStack: FlowState[] = [];
let currentIndex = -1;
let isUndoRedoInProgress = false;

//  Initialize history
export const initHistory = (nodes: Node[], edges: Edge[]) => {
  historyStack = [
    {
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges))
    }
  ];
  currentIndex = 0;
};

/**
 * Add a new operation to the history
 */
export const addHistory = (nodes: Node[], edges: Edge[]) => {
  console.log('addHistory add record')
  if (isUndoRedoInProgress) {
    isUndoRedoInProgress = false;
    return;
  }
  const newState = {
    nodes: JSON.parse(JSON.stringify(nodes)),
    edges: JSON.parse(JSON.stringify(edges))
  };

  //  Stricter state change detection
  const prevState = currentIndex >= 0 ? historyStack[currentIndex] : null;
  if (prevState && prevState.nodes.length === newState.nodes.length && prevState.edges.length === newState.edges.length && JSON.stringify(prevState.nodes) === JSON.stringify(newState.nodes) && JSON.stringify(prevState.edges) === JSON.stringify(newState.edges)) {
    console.log('[History] State unchanged, skip saving');
    return;
  }

  //  Clear operations after the current index (if any redo operations are pending)
  const removedCount = historyStack.length - (currentIndex + 1);
  historyStack.splice(currentIndex + 1);
  historyStack.push(newState);
  currentIndex = historyStack.length - 1;

  console.log(`[History] New, currentIndex=${currentIndex}, node count=${nodes.length}, edge count=${edges.length}, removed records=${removedCount}, call stack:`);
};

/**
 * Undo operation
 */
export const onUndo = (): FlowState | null => {
  if (currentIndex <= 0) {
    return null;
  }

  isUndoRedoInProgress = true;
  const prevIndex = currentIndex - 1;
  const prevState = historyStack[prevIndex];

  currentIndex = prevIndex;
  return {
    nodes: [...prevState.nodes],
    edges: [...prevState.edges]
  };
};

/**
 * Redo operation
 */
export const onRedo = (): FlowState | null => {
  if (currentIndex >= historyStack.length - 1) {
    return null;
  }

  isUndoRedoInProgress = true;
  currentIndex++;
  const nextState = historyStack[currentIndex];

  return nextState;
};

/**
 * Get current history state
 */
export const getCurrentHistory = (): FlowState | null => {
  if (currentIndex < 0) return null;
  return historyStack[currentIndex];
};

/**
 * Clear history
 */
export const clearHistory = () => {
  historyStack.length = 0;
  currentIndex = -1;
};
