import type { Permission } from '@opencode-ai/sdk'

export function PermissionDialog({ permission, onRespond }: {
  permission: Permission
  onRespond: (id: string, r: 'once' | 'always' | 'reject') => void
}) {
  return (
    <div className="perm">
      <div className="perm-title">{permission.title}</div>
      <div className="perm-actions">
        <button onClick={() => onRespond(permission.id, 'once')}>Allow once</button>
        <button onClick={() => onRespond(permission.id, 'always')}>Allow always</button>
        <button className="danger" onClick={() => onRespond(permission.id, 'reject')}>Deny</button>
      </div>
    </div>
  )
}
