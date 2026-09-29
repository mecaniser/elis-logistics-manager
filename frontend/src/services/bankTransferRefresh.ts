type Transfer = {id:string; bank_session?:{profile_id:string}|null}
type Phase = 'returned' | 'confirmed'

/** Once per transfer phase; a later confirmation waits for an earlier read. */
export function createTransferProfileRefresher() {
  const requests = new Map<string, Promise<void>>()
  const profiles = new Map<string, Promise<void>>()
  return (draft:Transfer, phase:Phase, sync:(profileId:string)=>Promise<void>):Promise<void> => {
    const profileId = draft.bank_session?.profile_id
    if (!profileId) return Promise.resolve()
    const key = `${draft.id}:${profileId}:${phase}`
    const existing = requests.get(key)
    if (existing) return existing
    const request = (profiles.get(profileId) || Promise.resolve()).catch(()=>undefined).then(()=>sync(profileId))
    requests.set(key, request)
    profiles.set(profileId, request)
    void request.catch(()=>{ if (requests.get(key) === request) requests.delete(key) }).finally(()=>{
      if (profiles.get(profileId) === request) profiles.delete(profileId)
    })
    return request
  }
}
