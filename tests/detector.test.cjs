const test=require('node:test'),assert=require('node:assert/strict'),{detect}=require('../frontend/assets/ball-detector.js');
test('colour candidate finds compact ball and rejects streak/background',()=>{
 const a=new Uint8ClampedArray(40*40*4);function pixel(x,y){a[(y*40+x)*4]=220;}
 for(let y=10;y<15;y++)for(let x=10;x<15;x++)pixel(x,y);
 for(let x=0;x<20;x++)pixel(x,30);pixel(35,35);
 const result=detect(a,40,40,[220,0,0],20);assert.equal(result.length,1);assert.equal(result[0].x,12);assert.equal(result[0].y,12);
 assert.equal(detect(a,40,40,[0,255,0],20).length,0);
});
