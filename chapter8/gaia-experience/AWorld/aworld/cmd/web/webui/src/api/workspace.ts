import { request } from '../utils/http';

/**
 * Workspace tree node data structure
 */
export interface WorkspaceTreeResponse {
  id: string;          //Node ID
  name: string;        //Node name
  type: string;        //Node type (dir/file)
  parentId: string | null; //Parent node ID
  depth: number;       //Node depth
  expanded: boolean;   //Expanded or not
  children: WorkspaceTreeResponse[]; //Child node list
}

/**
 * Request parameters for Get Artifact
 */
export interface ArtifactQueryRequest {
  artifact_types: string[];    //Artifact type
  artifact_ids: string[];    // Artifact ID
}

/**
 * Request parameters for Create Artifact
 */
export interface ArtifactCreateRequest {
  name: string;    //Artifact name
  type: string;    //Artifact type
  content: any;    //Artifact content
}

/**
 * Response data for Create Artifact
 */
export interface ArtifactCreateResponse {
  id: string;                     //Created Artifact ID
  status: 'success' | 'failed';   //Operation status
  message?: string;               //Optional status message
}

/**
 * Get workspace tree
 */
export const getWorkspaceTree = (sessionId: string) =>
  request(`api/workspaces/${sessionId}/tree`);


/**
 * Get workspace artifacts
 */
export const getWorkspaceArtifacts = (sessionId: string, body: ArtifactQueryRequest) =>
  request(`api/workspaces/${sessionId}/artifacts`, {
    method: 'POST',
    body
  });


/**
 * Create workspace artifact
 */
export const createArtifact = (workspaceId: string, body: ArtifactCreateRequest) =>
  request(`api/workspaces/${workspaceId}/artifacts`, {
    method: 'POST',
    body
  });
