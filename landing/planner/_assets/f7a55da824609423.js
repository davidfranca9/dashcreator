(globalThis["webpackChunk_canva_web"] = globalThis["webpackChunk_canva_web"] || []).push([[97668],{

/***/ 634217:
function(_, __, __webpack_require__) {__webpack_require__.n_x = __webpack_require__.n;const __web_req__ = __webpack_require__;__web_req__(905716);globalThis._5f74ec40302898c5a55451c9fbd04240 = globalThis._5f74ec40302898c5a55451c9fbd04240 || {};(function(__c) {var DKc=__webpack_require__(622889).EW;__c.DZ=class{static G(a){__c.L(a,{step:DKc})}get kind(){return"point"}clone({mc:a=this.mc,xc:b=this.xc,bj:c=this.bj,Ud:d=this.Ud,inverse:e=this.inverse}){return new __c.DZ({mc:a,xc:b,bj:c,Ud:d,inverse:e})}snapshot(){const a=this.mc(),b=this.xc();return new __c.DZ({mc:()=>a,xc:()=>b,bj:this.bj,Ud:this.Ud,inverse:this.inverse})}get(a){const b=this.mc();var c=b.indexOf(a);c=this.inverse?b.length-1-c:c;__c.w(c!==-1,`value ${a} must exist in domain`);const [d,e]=this.xc();a=b.length===1?.5:this.bj();return d+
(a*this.step+c*this.step)*Math.sign(e-d)}get step(){const a=this.mc().length+2*this.bj(),[b,c]=this.xc();return Math.abs(c-b)/Math.max(a-1,1)}wS(a,b,c){__c.w(a.index!==b.index);const d=this.bj(),e=(b.center-a.center)/(b.index-a.index);return[a.center-(d+a.index)*e,b.center+(d+c-b.index-1)*e]}vS(a,b,c){const d=this.bj();return[b,a.center+(a.center-b)/(a.index+d)*(d+c-a.index-1)]}uS(a,b,c){const d=this.bj();return[a.center-(b-a.center)/(c-a.index-1+d)*(d+a.index),b]}constructor({mc:a,xc:b,bj:c,Ud:d,
inverse:e=!1}){__c.DZ.G(this);this.mc=a;this.xc=b;this.bj=c;this.Ud=d;this.inverse=e}};
}).call(globalThis, globalThis._5f74ec40302898c5a55451c9fbd04240);}

}])
//# sourceMappingURL=sourcemaps/f7a55da824609423.js.map