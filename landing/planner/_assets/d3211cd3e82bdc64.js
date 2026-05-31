(globalThis["webpackChunk_canva_web"] = globalThis["webpackChunk_canva_web"] || []).push([[77828],{

/***/ 385379:
function(_, __, __webpack_require__) {__webpack_require__.n_x = __webpack_require__.n;const __web_req__ = __webpack_require__;__web_req__(905716);__web_req__(822995);globalThis._5f74ec40302898c5a55451c9fbd04240 = globalThis._5f74ec40302898c5a55451c9fbd04240 || {};(function(__c) {var URc=async function(a,b,c){const d=TRc()();try{const e=__c.y(a.lk.context),f=d.r(await d.s(a.fetch(b.url,{signal:c}))),g=d.r(await d.s(f.arrayBuffer()));return e.decodeAudioData(g)}finally{d.s()}},WRc=function(a,b,c,d){if(d){var e=a.cache.get(b);e||(e={buffer:c,U1:new Set},c.catch(VRc.wrap(()=>{a.cache.delete(b)})),a.cache.set(b,e));e.U1.add(d);d.addEventListener("abort",()=>{e?.U1.delete(d);e&&e.U1.size===0&&a.cache.delete(b);e=void 0},{once:!0})}},VRc=__webpack_require__(815703).F;var TRc=__webpack_require__(929846)._;var XRc;
XRc=class{async xc(a,b,c){const d=TRc()();try{__c.w(b.ba>=0&&b.L>=0);const m=__c.Hu(this.Rk,a);if(m){var e=this.cache.get(a)?.buffer||URc(this,m,c);WRc(this,a,e,c);var f=d.r(await d.s(e)),g=b.L-f.duration*1E6;if(b.ba===0&&(g>=0||Math.abs(g)<=100))return f;var h=b.L/1E6*f.sampleRate;if(h<=0)return f;var k=new AudioBuffer({length:h,numberOfChannels:f.numberOfChannels,sampleRate:f.sampleRate}),l=Math.floor(f.sampleRate*b.ba/1E6);for(a=0;a<f.numberOfChannels;a++){const n=f.getChannelData(a).subarray(l,l+
h);k.copyToChannel(n,a)}return k}}finally{d.s()}}constructor(a,b,c=__c.MOc){this.lk=a;this.Rk=b;this.fetch=c;this.cache=new Map}};__c.GEa={};__c.GEa.lCb=XRc;
}).call(globalThis, globalThis._5f74ec40302898c5a55451c9fbd04240);}

}])
//# sourceMappingURL=sourcemaps/d3211cd3e82bdc64.js.map