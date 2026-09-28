import {useEffect,useRef,useState} from 'react'
import {dateKey,periodPresets,reportingRange,validRange} from './reportingPeriod'
import './ReportingPeriodPicker.css'
export default function ReportingPeriodPicker({start,end,preset,onApply}:{start:string;end:string;preset:string;onApply:(start:string,end:string,preset:string)=>void}) {
 const [open,setOpen]=useState(false)
 const [position,setPosition]=useState({top:0,left:0})
 const [draft,setDraft]=useState({start,end})
 const [selected,setSelected]=useState(preset)
 const [month,setMonth]=useState(start.slice(0,7))
 const [pickingEnd,setPickingEnd]=useState(false)
 const root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null)
 const close=()=>{setOpen(false);trigger.current?.focus()}
 useEffect(()=>{if(!open)return;const outside=(e:PointerEvent)=>{if(!root.current?.contains(e.target as Node))setOpen(false)};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside)},[open])
 const base=new Date(`${month}-01T12:00:00`)
 const year=base.getFullYear(),m=base.getMonth(),offset=(base.getDay()+6)%7
 const count=new Date(year,m+1,0).getDate()
 const years=Array.from(new Set([...Array.from({length:31},(_,i)=>new Date().getFullYear()-20+i),year])).sort((a,b)=>a-b)
 const move=(n:number)=>setMonth(dateKey(new Date(year,m+n,1,12)).slice(0,7))
 const pick=(day:string)=>{setSelected('custom');if(!pickingEnd){setDraft({start:day,end:day});setPickingEnd(true)}else{setDraft({start:day<draft.start?day:draft.start,end:day<draft.start?draft.start:day});setPickingEnd(false)}}
 const name=periodPresets.find(([key])=>key===preset)?.[1]||'Custom dates'
 return <div className="reporting-picker" ref={root} onKeyDown={e=>{if(e.key==='Escape'&&open){e.stopPropagation();close()}}}>
 <button ref={trigger} type="button" className="finance-secondary reporting-trigger" aria-haspopup="dialog" aria-expanded={open} onClick={()=>{if(open)close();else{const rect=trigger.current!.getBoundingClientRect();setPosition({top:window.innerWidth<=600?80:Math.max(16,Math.min(rect.bottom+8,window.innerHeight-480)),left:Math.max(16,Math.min(rect.left,window.innerWidth-512))});setDraft({start,end});setSelected(preset);setMonth(start.slice(0,7));setPickingEnd(false);setOpen(true)}}}><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></svg>{name}<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{transform:open?'rotate(180deg)':undefined}}><path d="m6 9 6 6 6-6"/></svg></button>
 {open&&<div role="dialog" aria-label="Choose reporting period" className="reporting-popover" style={{top:position.top,left:position.left,maxHeight:`calc(100dvh - ${position.top+16}px)`}}><div className="reporting-presets" aria-label="Period presets">{periodPresets.map(([key,label])=><button type="button" key={key} aria-pressed={selected===key} onClick={()=>{const range=reportingRange(key);setDraft(range);setSelected(key);setMonth(range.start.slice(0,7));setPickingEnd(false)}}>{label}</button>)}<button type="button" aria-pressed={selected==='custom'} onClick={()=>{setSelected('custom');setPickingEnd(false)}}>Custom dates</button></div>
 <div className="reporting-calendar"><div className="reporting-month-nav"><button type="button" aria-label="Previous calendar month" onClick={()=>move(-1)}>‹</button><select aria-label="Calendar month" value={m} onChange={e=>setMonth(dateKey(new Date(year,Number(e.target.value),1,12)).slice(0,7))}>{Array.from({length:12},(_,i)=><option key={i} value={i}>{new Date(2026,i,1).toLocaleString('en-US',{month:'long'})}</option>)}</select><select aria-label="Calendar year" value={year} onChange={e=>setMonth(dateKey(new Date(Number(e.target.value),m,1,12)).slice(0,7))}>{years.map(y=><option key={y}>{y}</option>)}</select><button type="button" aria-label="Next calendar month" onClick={()=>move(1)}>›</button></div>
 <div className="reporting-days">{['Mo','Tu','We','Th','Fr','Sa','Su'].map(d=><span key={d} className="reporting-weekday">{d}</span>)}{Array.from({length:offset},(_,i)=><span key={`blank-${i}`}/>)}{Array.from({length:count},(_,i)=>{const day=dateKey(new Date(year,m,i+1,12));return <button type="button" key={day} aria-label={day} aria-pressed={day>=draft.start&&day<=draft.end} aria-current={day===dateKey(new Date())?'date':undefined} className={day===draft.start||day===draft.end?'range-edge':day>draft.start&&day<draft.end?'in-range':''} onClick={()=>pick(day)}>{i+1}</button>})}</div>
 <div className="reporting-range-inputs"><label>From<input aria-label="Period start" type="date" value={draft.start} onChange={e=>{setDraft({...draft,start:e.target.value});setSelected('custom')}}/></label><label>To<input aria-label="Period end" type="date" value={draft.end} onChange={e=>{setDraft({...draft,end:e.target.value});setSelected('custom')}}/></label></div>
 <div className="reporting-picker-footer"><span aria-live="polite">{!validRange(draft.start,draft.end)?'Choose a valid start and end date.':pickingEnd?'Select the end date.':''}</span><button type="button" className="finance-secondary" onClick={close}>Cancel</button><button type="button" className="finance-primary" disabled={!validRange(draft.start,draft.end)} onClick={()=>{onApply(draft.start,draft.end,selected);close()}}>Apply</button></div></div></div>}
 </div>
}
