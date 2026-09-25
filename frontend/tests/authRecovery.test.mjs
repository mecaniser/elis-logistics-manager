import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
const source = fs.readFileSync(new URL('../src/services/api.ts', import.meta.url),'utf8')
const handler = source.slice(source.indexOf('const handleAuthFailure'),source.indexOf('const api ='))
const compiled = ts.transpileModule(handler,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText
function setup(check) {
  const redirected=[]
  const window={location:{pathname:'/bank-monitor',search:'',hash:'',replace:p=>redirected.push(p)}}
  const run=new Function('axios','window',compiled+'; return handleAuthFailure')({get:check},window)
  return {run,redirected}
}
for (const session of [{username:'local-dev',authentication_enabled:false},{username:'signed-user'}]) {
  test(`valid shell session does not redirect a protected endpoint failure: ${session.username}`,async()=>{
    const {run,redirected}=setup(async()=>({data:session}))
    const error={response:{status:401}}
    await assert.rejects(run(error),e=>e===error)
    assert.deepEqual(redirected,[])
  })
}
test('expired shell session retains login recovery and return path',async()=>{
  const {run,redirected}=setup(async()=>{throw new Error('Unauthorized')})
  const error={response:{status:401}}
  await assert.rejects(run(error),e=>e===error)
  assert.deepEqual(redirected,['/login?from=%2Fbank-monitor&reason=session-expired'])
})
test('non-auth failures do not probe or redirect',async()=>{
  let checked=false
  const {run,redirected}=setup(async()=>{checked=true})
  await assert.rejects(run({response:{status:403}}))
  assert.equal(checked,false)
  assert.deepEqual(redirected,[])
})
