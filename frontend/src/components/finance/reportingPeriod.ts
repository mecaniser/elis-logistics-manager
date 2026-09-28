export const periodPresets = [ ['week','This week'],['previous-week','Previous week'],['month','This month'],['previous-month','Previous month'],['quarter','This quarter'],['previous-quarter','Previous quarter'],['year','This year'],['previous-year','Previous year'],['30-days','Last 30 days'],['90-days','Last 90 days'] ] as const
export function dateKey(d:Date) { return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}` }
export function reportingRange(p:string,now=new Date()) {
 const end=new Date(now.getFullYear(),now.getMonth(),now.getDate(),12),start=new Date(end)
 if(p==='week'||p==='previous-week') {start.setDate(start.getDate()-(start.getDay()+6)%7);if(p==='previous-week'){end.setTime(start.getTime());end.setDate(end.getDate()-1);start.setDate(start.getDate()-7)}}
 else if(p==='month'||p==='previous-month'){start.setDate(1);if(p==='previous-month'){end.setTime(start.getTime());end.setDate(0);start.setMonth(start.getMonth()-1)}}
 else if(p==='quarter'||p==='previous-quarter'){start.setDate(1);start.setMonth(Math.floor(start.getMonth()/3)*3);if(p==='previous-quarter'){end.setTime(start.getTime());end.setDate(0);start.setMonth(start.getMonth()-3)}}
 else if(p==='year'||p==='previous-year'){start.setMonth(0,1);if(p==='previous-year'){end.setTime(start.getTime());end.setDate(0);start.setFullYear(start.getFullYear()-1)}}
 else if(p==='30-days'||p==='90-days')start.setDate(start.getDate()-(p==='30-days'?29:89))
 else throw new Error('Unknown reporting period')
 return {start:dateKey(start),end:dateKey(end)}
}
export function validRange(start:string,end:string) {
 const valid=(s:string)=>/^\d{4}-\d{2}-\d{2}$/.test(s)&&dateKey(new Date(`${s}T12:00:00`))===s
 return valid(start)&&valid(end)&&start<=end
}
