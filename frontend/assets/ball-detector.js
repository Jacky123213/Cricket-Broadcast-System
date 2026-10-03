/* Replaceable 2D colour-component candidate detector. No 3D or LBW inference. */
(function(root){
 function detect(data,width,height,colour,tolerance=70,minArea=3,maxArea=250){
  const mask=new Uint8Array(width*height),seen=new Uint8Array(mask.length),found=[];
  for(let i=0;i<mask.length;i++){const j=i*4;mask[i]=(data[j]-colour[0])**2+(data[j+1]-colour[1])**2+(data[j+2]-colour[2])**2<tolerance*tolerance?1:0;}
  for(let i=0;i<mask.length;i++){
   if(!mask[i]||seen[i])continue;
   const queue=[i];seen[i]=1;let sx=0,sy=0,minX=width,maxX=0,minY=height,maxY=0;
   for(let k=0;k<queue.length;k++){
    const n=queue[k],x=n%width,y=Math.floor(n/width);sx+=x;sy+=y;minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
    for(const q of [x>0?n-1:-1,x<width-1?n+1:-1,y>0?n-width:-1,y<height-1?n+width:-1])if(q>=0&&mask[q]&&!seen[q]){seen[q]=1;queue.push(q);}
   }
   const area=queue.length,w=maxX-minX+1,h=maxY-minY+1;
   if(area>=minArea&&area<=maxArea&&w/h>.45&&w/h<2.2&&area/(w*h)>.4)found.push({x:sx/area,y:sy/area,area,radius:Math.max(w,h)/2});
  }
  return found.sort((a,b)=>b.area-a.area).slice(0,8);
 }
 if(typeof module!=='undefined')module.exports={detect};else root.DRSBallDetector={detect};
})(typeof window!=='undefined'?window:globalThis);
