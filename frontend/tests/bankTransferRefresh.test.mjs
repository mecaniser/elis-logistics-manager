import assert from 'node:assert/strict'
import test from 'node:test'
import {createTransferProfileRefresher} from '../src/services/bankTransferRefresh.ts'

const draft = {id:'transfer-1', bank_session:{profile_id:'consolidated'}}
test('refreshes the bound profile once per return and confirmation, regardless of repeated events', async()=>{
  const refresh=createTransferProfileRefresher(), calls=[]
  const sync=async id=>{calls.push(id)}
  await Promise.all([refresh(draft,'returned',sync),refresh(draft,'returned',sync)])
  await Promise.all([refresh(draft,'confirmed',sync),refresh(draft,'confirmed',sync)])
  assert.deepEqual(calls,['consolidated','consolidated'])
  await refresh({id:'transfer-2',bank_session:{profile_id:'main-business'}},'confirmed',sync)
  assert.equal(calls.at(-1),'main-business')
})
test('confirmation waits for an in-flight return read and then gets newer balances', async()=>{
  const refresh=createTransferProfileRefresher(), calls=[]
  let release
  const gate=new Promise(resolve=>{release=resolve})
  const first=refresh(draft,'returned',async()=>{calls.push('return');await gate})
  const second=refresh(draft,'confirmed',async()=>{calls.push('confirmed')})
  await new Promise(resolve=>setImmediate(resolve))
  assert.deepEqual(calls,['return'])
  release();await Promise.all([first,second])
  assert.deepEqual(calls,['return','confirmed'])
})
test('failure permits retry and does not prevent a subsequent confirmed read',async()=>{
  const refresh=createTransferProfileRefresher()
  await assert.rejects(refresh(draft,'returned',async()=>{throw Error('offline')}))
  const calls=[]
  await refresh(draft,'returned',async id=>{calls.push(id)})
  await refresh(draft,'confirmed',async id=>{calls.push(id)})
  assert.deepEqual(calls,['consolidated','consolidated'])
})
test('legacy transfers without a profile never refresh an arbitrary selected login',async()=>{
  const refresh=createTransferProfileRefresher()
  await refresh({id:'legacy'},'confirmed',async()=>{assert.fail('no bound profile')})
})
