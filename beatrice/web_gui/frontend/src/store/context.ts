import React from 'react';
import { GraphStore } from './graphStore';

export const GraphStoreContext = React.createContext<GraphStore>(null as unknown as GraphStore);

export function useGraph(): GraphStore {
  return React.useContext(GraphStoreContext);
}
