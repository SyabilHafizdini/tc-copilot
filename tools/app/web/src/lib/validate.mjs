// Shared graph-document validation. Plain JS on purpose: imported by the
// browser bundle AND executed directly by the zero-dependency CLI scripts.

function isPlainObject(v) {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

const HEX_COLOR = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

function checkString(errors, path, value) {
  if (typeof value !== 'string' || value.length === 0) {
    errors.push(`${path}: required non-empty string`)
    return false
  }
  return true
}

function checkStringArray(errors, path, value) {
  if (!Array.isArray(value)) {
    errors.push(`${path}: expected an array of strings`)
    return
  }
  value.forEach((v, i) => {
    if (typeof v !== 'string' || v.length === 0) {
      errors.push(`${path}[${i}]: required non-empty string`)
    }
  })
}

/**
 * Validate an already-parsed JSON value against the graph template.
 * Returns an array of error strings; empty array means valid.
 */
export function validateGraph(data) {
  if (!isPlainObject(data)) {
    return ['root: expected an object with "nodes" and "edges" arrays']
  }
  const errors = []

  if (data.meta !== undefined) {
    if (!isPlainObject(data.meta)) {
      errors.push('meta: expected an object')
    } else {
      if (data.meta.title !== undefined && typeof data.meta.title !== 'string') {
        errors.push('meta.title: expected a string')
      }
      if (data.meta.description !== undefined && typeof data.meta.description !== 'string') {
        errors.push('meta.description: expected a string')
      }
      if (data.meta.typeColors !== undefined) {
        if (!isPlainObject(data.meta.typeColors)) {
          errors.push('meta.typeColors: expected an object')
        } else {
          for (const [nodeType, color] of Object.entries(data.meta.typeColors)) {
            if (typeof color !== 'string' || !HEX_COLOR.test(color)) {
              errors.push(`meta.typeColors.${nodeType}: expected a hex color like "#3B82F6"`)
            }
          }
        }
      }
    }
  }

  if (data.presets !== undefined) {
    if (!Array.isArray(data.presets)) {
      errors.push('presets: expected an array')
    } else {
      const presetNames = new Set()
      data.presets.forEach((p, i) => {
        if (!isPlainObject(p)) {
          errors.push(`presets[${i}]: expected an object`)
          return
        }
        checkString(errors, `presets[${i}].name`, p.name)
        if (typeof p.name === 'string' && p.name.length > 0) {
          if (presetNames.has(p.name)) {
            errors.push(`presets[${i}].name: duplicate name "${p.name}"`)
          }
          presetNames.add(p.name)
        }
        if (p.description !== undefined && typeof p.description !== 'string') {
          errors.push(`presets[${i}].description: expected a string`)
        }
        if (p.search !== undefined && typeof p.search !== 'string') {
          errors.push(`presets[${i}].search: expected a string`)
        }
        if (p.default !== undefined && typeof p.default !== 'boolean') {
          errors.push(`presets[${i}].default: expected a boolean`)
        }
        if (p.nodeTypes !== undefined) checkStringArray(errors, `presets[${i}].nodeTypes`, p.nodeTypes)
        if (p.edgeTypes !== undefined) checkStringArray(errors, `presets[${i}].edgeTypes`, p.edgeTypes)
      })
    }
  }

  const nodesOk = Array.isArray(data.nodes)
  const edgesOk = Array.isArray(data.edges)
  if (!nodesOk) errors.push('nodes: required array')
  if (!edgesOk) errors.push('edges: required array')
  if (!nodesOk || !edgesOk) return errors

  const nodeIds = new Set()
  data.nodes.forEach((n, i) => {
    if (!isPlainObject(n)) {
      errors.push(`nodes[${i}]: expected an object`)
      return
    }
    if (checkString(errors, `nodes[${i}].nodeId`, n.nodeId)) {
      if (nodeIds.has(n.nodeId)) {
        errors.push(`nodes[${i}].nodeId: duplicate id "${n.nodeId}"`)
      }
      nodeIds.add(n.nodeId)
    }
    checkString(errors, `nodes[${i}].nodeType`, n.nodeType)
    checkString(errors, `nodes[${i}].displayLabel`, n.displayLabel)
    if (n.properties !== undefined && !isPlainObject(n.properties)) {
      errors.push(`nodes[${i}].properties: expected an object`)
    }
    if (n.content !== undefined && typeof n.content !== 'string') {
      errors.push(`nodes[${i}].content: expected a string`)
    }
  })

  const edgeIds = new Set()
  data.edges.forEach((e, i) => {
    if (!isPlainObject(e)) {
      errors.push(`edges[${i}]: expected an object`)
      return
    }
    if (checkString(errors, `edges[${i}].edgeId`, e.edgeId)) {
      if (edgeIds.has(e.edgeId)) {
        errors.push(`edges[${i}].edgeId: duplicate id "${e.edgeId}"`)
      }
      edgeIds.add(e.edgeId)
    }
    checkString(errors, `edges[${i}].edgeType`, e.edgeType)
    for (const key of ['fromNodeId', 'toNodeId']) {
      if (checkString(errors, `edges[${i}].${key}`, e[key]) && !nodeIds.has(e[key])) {
        errors.push(`edges[${i}].${key}: "${e[key]}" not found in nodes`)
      }
    }
    if (e.properties !== undefined && !isPlainObject(e.properties)) {
      errors.push(`edges[${i}].properties: expected an object`)
    }
  })

  return errors
}

/** Fill optional fields with defaults. Call only after validateGraph returns []. */
export function normalizeGraph(data) {
  return {
    meta: data.meta,
    presets: data.presets,
    nodes: data.nodes.map((n) => ({ ...n, properties: n.properties ?? {} })),
    edges: data.edges.map((e) => ({ ...e, properties: e.properties ?? {} })),
  }
}
