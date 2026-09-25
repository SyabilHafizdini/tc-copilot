/** Nested folder/file tree built from flat doc refs (real filesystem paths,
 * e.g. "testcases/sit/production-monitoring/1.1.3.1.1-AC01-01"). Pure —
 * no React, no I/O — so it is trivial to unit test in isolation. */

export type FolderNode = { kind: 'folder'; name: string; path: string; children: FileNode[] }
export type FileLeaf = { kind: 'file'; name: string; ref: string }
export type FileNode = FolderNode | FileLeaf

/** Splits each ref on "/" and merges shared prefixes into folders. Folders
 * sort before files, then everything sorts alphabetically by name — applied
 * recursively at every level, including the returned top-level array. */
export function buildFileTree(refs: string[]): FileNode[] {
  const root: FolderNode = { kind: 'folder', name: '', path: '', children: [] }

  for (const ref of refs) {
    const segments = ref.split('/').filter((s) => s.length > 0)
    if (segments.length === 0) continue

    let cursor = root
    for (let i = 0; i < segments.length - 1; i++) {
      const name = segments[i]
      const path = segments.slice(0, i + 1).join('/')
      let next = cursor.children.find(
        (c): c is FolderNode => c.kind === 'folder' && c.name === name,
      )
      if (!next) {
        next = { kind: 'folder', name, path, children: [] }
        cursor.children.push(next)
      }
      cursor = next
    }

    const name = segments[segments.length - 1]
    cursor.children.push({ kind: 'file', name, ref })
  }

  sortTree(root.children)
  return root.children
}

function sortTree(nodes: FileNode[]): void {
  nodes.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1
    return a.name.localeCompare(b.name)
  })
  for (const node of nodes) {
    if (node.kind === 'folder') sortTree(node.children)
  }
}
