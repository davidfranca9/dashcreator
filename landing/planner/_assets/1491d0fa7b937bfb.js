(globalThis["webpackChunk_canva_web"] = globalThis["webpackChunk_canva_web"] || []).push([[63116],{

/***/ 92846:
function(_, __, __webpack_require__) {__webpack_require__.n_x = __webpack_require__.n;const __web_req__ = __webpack_require__;__web_req__(905716);globalThis._5f74ec40302898c5a55451c9fbd04240 = globalThis._5f74ec40302898c5a55451c9fbd04240 || {};(function(__c) {var fFc,gFc,hFc;fFc=(a,b)=>a.top>=b.top-1E-4&&a.top+a.height<=b.top+b.height+1E-4&&a.left>=b.left-1E-4&&a.left+a.width<=b.left+b.width+1E-4;gFc=(a,b)=>{switch(a.type){case "rect":case "shape":return a.width*a.height>=.05*b.width*b.height;case "design":case "chart":case "embed":case "grid":case "group":case "layout":case "line":case "sheet":case "table":case "text":case "controlled":return!1;default:throw new __c.z(a.type);}};
hFc=(a,b)=>{const c=[],d=[],e=new Set;for(const g of a){a=g;var f=b;if(gFc(a,f)&&a.left<=1E-4&&a.top<=1E-4&&a.left+a.width>=f.width-1E-4&&a.top+a.height>=f.height-1E-4)c.push(g);else{if(a=gFc(g,b)){a:{for(a=d.length-1;a>=0;a--){f=d[a];if(g.top>f.top+f.height)break;if(fFc(g,f)){a=!0;break a}}a=!1}a=!a}a?d.push(g):e.add(g)}}return{gGb:c,nJb:d,uXb:e}};
__c.iFc=(a,b,c=1)=>{b=__c.Fj(b);a=a.sort((k,l)=>Math.abs(k.top-l.top)<3?c===1?k.left-l.left:l.left-k.left:k.top-l.top);const {gGb:d,nJb:e,uXb:f}=hFc(a,b);b=new Map;let g=d.length>0;for(var h of e){const k=[];for(const l of f){if(l.top>h.top+h.height)break;fFc(l,h)&&(k.push(l),f.delete(l))}k.length>0&&(g=!0);b.set(h,k)}if(!g)return a;for(const k of a)(h=b.get(k))?(d.push(k),d.push(...h)):f.has(k)&&d.push(k);return d};
}).call(globalThis, globalThis._5f74ec40302898c5a55451c9fbd04240);}

}])
//# sourceMappingURL=sourcemaps/1491d0fa7b937bfb.js.map