(globalThis["webpackChunk_canva_web"] = globalThis["webpackChunk_canva_web"] || []).push([[37329],{

/***/ 341086:
function(_, __, __webpack_require__) {__webpack_require__.n_x = __webpack_require__.n;const __web_req__ = __webpack_require__;__web_req__(905716);globalThis._5f74ec40302898c5a55451c9fbd04240 = globalThis._5f74ec40302898c5a55451c9fbd04240 || {};(function(__c) {var w=__c.w;var Hud,Jud,Iud,c8;Hud=function(a){return(Math.ceil(Math.sqrt(Math.max(1,Math.ceil(a/2))*4)/2)*2)**2};
Jud=function(a,b){const c=Math.ceil(b/1E6*200),d=Math.ceil(Math.ceil(b/1E6*a.sampleRate)/c),e=Array.from({length:a.numberOfChannels},(g,h)=>{g=Math.floor(0*a.sampleRate);const k=Math.min(Math.floor((0+b)/1E6*a.sampleRate),a.length);return a.getChannelData(h).subarray(g,k)}),f=new Float32Array(Hud(c));for(let g=0;g<c;g++){const h=Iud(e,g,d),k=g*2;f[k]=h.max;f[k+1]=h.min}return{buffer:f,L2:c}};
Iud=function(a,b,c){var d=Math.floor(b*c);b=Math.min(Math.floor((b+1)*c),a[0].length,d+500);c=Infinity;let e=-Infinity;for(;d<b;d++){let f=0;for(let g=0;g<a.length;++g)f+=a[g][d];c=Math.min(c,f);e=Math.max(e,f)}return{min:isFinite(c)?c/a.length:0,max:isFinite(e)?e/a.length:0}};
c8=class{static jRb(a){w(!0);w(!0);w(!0);const b=a.duration*1E6;w(a.duration*1E6>=b,"Duration of {}s exceeds audio length of {}s",b/1E6,a.duration);const {buffer:c,L2:d}=Jud(a,b);return new c8(c,0,d,200)}trim(a,b){w(a>=0&&b>=0);a=Math.floor(a/1E6*this.oda);return new c8(this.buffer,this.Sva+a,Math.min(Math.ceil(b/1E6*this.oda),this.L2-a),this.oda)}split(a){w(a>0);if(a<=1)return[this];const b=Math.ceil(this.L2/a);return Array.from({length:Math.ceil(a)},(c,d)=>{c=this.Sva+d*b;return new c8(this.buffer,
c,Math.min(c+b,this.Sva+this.L2)-c,this.oda)})}repeat(a){w(a>0);if(a<=1)return this;const b=this.L2*a,c=new Float32Array(Hud(b));var d=this.Sva*2;d=this.buffer.subarray(d,d+this.L2*2);for(let e=0;e<a;e++)c.set(d,e*d.length);return new c8(c,0,b,this.oda)}constructor(a,b,c,d){this.buffer=a;this.Sva=b;this.L2=c;this.oda=d;w(c*2<=a.length)}};__c.zEa={};__c.zEa.UDb=c8;
}).call(globalThis, globalThis._5f74ec40302898c5a55451c9fbd04240);}

}])
//# sourceMappingURL=sourcemaps/42351a36641de96c.js.map