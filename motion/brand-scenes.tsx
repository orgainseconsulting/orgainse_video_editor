import React from "react";
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {BgMesh, Grade, Grain, Vignette} from "../upstream/remotion-skill/examples/src/components/Layers";

const ramp = (f:number,a:number,b:number) => interpolate(f,[a,b],[0,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp",easing:Easing.bezier(.16,1,.3,1)});

export function BrandScene({variant}) {
  const frame = useCurrentFrame();
  const {width,height} = useVideoConfig();
  const data = window.sceneData || {};
  const portrait = height > width;
  const product = variant === "StudioProductFocus";
  const end = variant === "StudioBrandClose";
  const ink = "#e9f4ff", blue = "#49c8ff";
  const title = data.headline || (product ? "See it in action." : end ? "Explore the product." : "Meet the product.");
  const words = title.split(/\s+/);
  const rise = spring({frame,fps:30,config:{damping:22,stiffness:100,mass:.85}});
  const opacity = ramp(frame,0,19);
  const left = width*.068;
  const size = (portrait ? 84 : product ? 86 : 130) * Math.min(1, (product ? 40 : 50)/title.length);
  return <AbsoluteFill style={{background:"#081427",overflow:"hidden",fontFamily:"Inter, Segoe UI, Arial, sans-serif",color:ink}}>
    <BgMesh/>
    <AbsoluteFill style={{background:"linear-gradient(114deg,rgba(1,20,41,.95),rgba(8,34,86,.65) 64%,rgba(5,66,95,.7))"}}/>
    <div style={{position:"absolute",inset:0,opacity:.14,backgroundImage:"linear-gradient(90deg,#6484ba 1px,transparent 1px),linear-gradient(#6484ba 1px,transparent 1px)",backgroundSize:"88px 88px",maskImage:"linear-gradient(120deg,transparent 14%,black 92%)"}}/>
    <div style={{position:"absolute",width:width*.74,height:width*.74,border:"2px solid rgba(67,169,255,.2)",borderRadius:"50%",right:-width*.29,top:-height*.13,transform:"scale("+(.86+.18*rise)+")"}}/>
    {data.logo && <img src="/current-logo" style={{position:"absolute",left,top:height*.09,width:portrait?260:330,height:80,objectFit:"contain",objectPosition:"left center",opacity}}/>}
    <div style={{position:"absolute",left,top:height*(product ? (portrait?.22:.34) : .36),width:width*(product&&!portrait ? .35 : .85)}}>
      <div style={{width:74*rise,height:5,background:blue,marginBottom:27}}/>
      <div style={{fontSize:size,fontWeight:750,letterSpacing:"-.048em",lineHeight:1.04}}>
        {words.map((word,i) => {const a=ramp(frame,4+i*2,24+i*2);return <React.Fragment key={i}><span style={{display:"inline-block",opacity:a,transform:"translateY("+(1-a)*32+"px)",color:end&&i===words.length-1?blue:ink}}>{word}</span>{" "}</React.Fragment>;})}
      </div>
      {data.subhead && <div style={{fontSize:portrait?31:34,color:"#c5daed",lineHeight:1.35,marginTop:23,maxWidth:product?610:1120,opacity:ramp(frame,16,36)}}>{data.subhead}</div>}
    </div>
    {product && <div style={{position:"absolute",left:width*(portrait?.068:.46),right:width*.045,top:height*(portrait?.49:.20),bottom:height*.13,borderRadius:24,padding:10,background:"#c4d5e4",boxShadow:"0 40px 110px rgba(0,0,0,.50)",opacity,transform:"perspective(1600px) translateY("+(1-rise)*96+"px) rotateY("+((1-rise)*-12)+"deg)"}}>
      {data.screen ? <img src="/current-screen" style={{width:"100%",height:"100%",display:"block",objectFit:"contain",borderRadius:16,background:"white"}}/> : <div style={{height:"100%",borderRadius:16,background:"linear-gradient(125deg,#206b8a,#1c335d)",display:"grid",placeItems:"center",fontSize:44,color:"#e2f3ff"}}>Product screen</div>}
    </div>}
    <Grade/><Vignette/><Grain/>
  </AbsoluteFill>;
}
export const StudioTypeReveal = () => <BrandScene variant="StudioTypeReveal"/>;
export const StudioProductFocus = () => <BrandScene variant="StudioProductFocus"/>;
export const StudioBrandClose = () => <BrandScene variant="StudioBrandClose"/>;
