/**
 * LiquidEther – Fluid simulation background.
 * Vanilla-JS port of react-bits/LiquidEther. Requires Three.js (global).
 */
(function () {
  'use strict';
  if (typeof THREE === 'undefined') { console.error('[LiquidEther] THREE.js not loaded'); return; }

  /* ── shaders ── */
  var face_vert = [
    'attribute vec3 position;',
    'uniform vec2 px;',
    'uniform vec2 boundarySpace;',
    'varying vec2 uv;',
    'precision highp float;',
    'void main(){',
    '  vec3 pos = position;',
    '  vec2 scale = 1.0 - boundarySpace * 2.0;',
    '  pos.xy = pos.xy * scale;',
    '  uv = vec2(0.5)+(pos.xy)*0.5;',
    '  gl_Position = vec4(pos, 1.0);',
    '}'
  ].join('\n');

  var line_vert = [
    'attribute vec3 position;',
    'uniform vec2 px;',
    'precision highp float;',
    'varying vec2 uv;',
    'void main(){',
    '  vec3 pos = position;',
    '  uv = 0.5 + pos.xy * 0.5;',
    '  vec2 n = sign(pos.xy);',
    '  pos.xy = abs(pos.xy) - px * 1.0;',
    '  pos.xy *= n;',
    '  gl_Position = vec4(pos, 1.0);',
    '}'
  ].join('\n');

  var mouse_vert = [
    'precision highp float;',
    'attribute vec3 position;',
    'attribute vec2 uv;',
    'uniform vec2 center;',
    'uniform vec2 scale;',
    'uniform vec2 px;',
    'varying vec2 vUv;',
    'void main(){',
    '  vec2 pos = position.xy * scale * 2.0 * px + center;',
    '  vUv = uv;',
    '  gl_Position = vec4(pos, 0.0, 1.0);',
    '}'
  ].join('\n');

  var advection_frag = [
    'precision highp float;',
    'uniform sampler2D velocity;',
    'uniform float dt;',
    'uniform bool isBFECC;',
    'uniform vec2 fboSize;',
    'uniform vec2 px;',
    'varying vec2 uv;',
    'void main(){',
    '  vec2 ratio = max(fboSize.x, fboSize.y) / fboSize;',
    '  if(isBFECC == false){',
    '    vec2 vel = texture2D(velocity, uv).xy;',
    '    vec2 uv2 = uv - vel * dt * ratio;',
    '    gl_FragColor = vec4(texture2D(velocity, uv2).xy, 0.0, 0.0);',
    '  } else {',
    '    vec2 spot_new = uv;',
    '    vec2 vel_old = texture2D(velocity, uv).xy;',
    '    vec2 spot_old = spot_new - vel_old * dt * ratio;',
    '    vec2 vel_new1 = texture2D(velocity, spot_old).xy;',
    '    vec2 spot_new2 = spot_old + vel_new1 * dt * ratio;',
    '    vec2 error = spot_new2 - spot_new;',
    '    vec2 spot_new3 = spot_new - error / 2.0;',
    '    vec2 vel_2 = texture2D(velocity, spot_new3).xy;',
    '    vec2 spot_old2 = spot_new3 - vel_2 * dt * ratio;',
    '    gl_FragColor = vec4(texture2D(velocity, spot_old2).xy, 0.0, 0.0);',
    '  }',
    '}'
  ].join('\n');

  var color_frag = [
    'precision highp float;',
    'uniform sampler2D velocity;',
    'uniform sampler2D palette;',
    'uniform vec4 bgColor;',
    'varying vec2 uv;',
    'void main(){',
    '  vec2 vel = texture2D(velocity, uv).xy;',
    '  float lenv = clamp(length(vel), 0.0, 1.0);',
    '  vec3 c = texture2D(palette, vec2(lenv, 0.5)).rgb;',
    '  vec3 outRGB = mix(bgColor.rgb, c, lenv);',
    '  float outA = mix(bgColor.a, 1.0, lenv);',
    '  gl_FragColor = vec4(outRGB, outA);',
    '}'
  ].join('\n');

  var divergence_frag = [
    'precision highp float;',
    'uniform sampler2D velocity;',
    'uniform float dt;',
    'uniform vec2 px;',
    'varying vec2 uv;',
    'void main(){',
    '  float x0 = texture2D(velocity, uv-vec2(px.x, 0.0)).x;',
    '  float x1 = texture2D(velocity, uv+vec2(px.x, 0.0)).x;',
    '  float y0 = texture2D(velocity, uv-vec2(0.0, px.y)).y;',
    '  float y1 = texture2D(velocity, uv+vec2(0.0, px.y)).y;',
    '  gl_FragColor = vec4((x1 - x0 + y1 - y0) * 0.5 / dt);',
    '}'
  ].join('\n');

  var externalForce_frag = [
    'precision highp float;',
    'uniform vec2 force;',
    'uniform vec2 center;',
    'uniform vec2 scale;',
    'uniform vec2 px;',
    'varying vec2 vUv;',
    'void main(){',
    '  vec2 circle = (vUv - 0.5) * 2.0;',
    '  float d = 1.0 - min(length(circle), 1.0);',
    '  d *= d;',
    '  gl_FragColor = vec4(force * d, 0.0, 1.0);',
    '}'
  ].join('\n');

  var poisson_frag = [
    'precision highp float;',
    'uniform sampler2D pressure;',
    'uniform sampler2D divergence;',
    'uniform vec2 px;',
    'varying vec2 uv;',
    'void main(){',
    '  float p0 = texture2D(pressure, uv + vec2(px.x*2.0, 0.0)).r;',
    '  float p1 = texture2D(pressure, uv - vec2(px.x*2.0, 0.0)).r;',
    '  float p2 = texture2D(pressure, uv + vec2(0.0, px.y*2.0)).r;',
    '  float p3 = texture2D(pressure, uv - vec2(0.0, px.y*2.0)).r;',
    '  float div = texture2D(divergence, uv).r;',
    '  gl_FragColor = vec4((p0+p1+p2+p3)/4.0 - div);',
    '}'
  ].join('\n');

  var pressure_frag = [
    'precision highp float;',
    'uniform sampler2D pressure;',
    'uniform sampler2D velocity;',
    'uniform vec2 px;',
    'uniform float dt;',
    'varying vec2 uv;',
    'void main(){',
    '  float p0 = texture2D(pressure, uv+vec2(px.x,0.0)).r;',
    '  float p1 = texture2D(pressure, uv-vec2(px.x,0.0)).r;',
    '  float p2 = texture2D(pressure, uv+vec2(0.0,px.y)).r;',
    '  float p3 = texture2D(pressure, uv-vec2(0.0,px.y)).r;',
    '  vec2 v = texture2D(velocity, uv).xy;',
    '  v = v - vec2(p0-p1, p2-p3)*0.5*dt;',
    '  gl_FragColor = vec4(v, 0.0, 1.0);',
    '}'
  ].join('\n');

  var viscous_frag = [
    'precision highp float;',
    'uniform sampler2D velocity;',
    'uniform sampler2D velocity_new;',
    'uniform float v;',
    'uniform vec2 px;',
    'uniform float dt;',
    'varying vec2 uv;',
    'void main(){',
    '  vec2 old = texture2D(velocity, uv).xy;',
    '  vec2 n0 = texture2D(velocity_new, uv+vec2(px.x*2.0,0.0)).xy;',
    '  vec2 n1 = texture2D(velocity_new, uv-vec2(px.x*2.0,0.0)).xy;',
    '  vec2 n2 = texture2D(velocity_new, uv+vec2(0.0,px.y*2.0)).xy;',
    '  vec2 n3 = texture2D(velocity_new, uv-vec2(0.0,px.y*2.0)).xy;',
    '  vec2 nv = 4.0*old + v*dt*(n0+n1+n2+n3);',
    '  nv /= 4.0*(1.0+v*dt);',
    '  gl_FragColor = vec4(nv, 0.0, 0.0);',
    '}'
  ].join('\n');

  /* ── helpers ── */
  function makePalette(stops) {
    var arr = (stops && stops.length) ? (stops.length === 1 ? [stops[0],stops[0]] : stops) : ['#fff','#fff'];
    var w = arr.length, data = new Uint8Array(w*4);
    for (var i=0;i<w;i++) {
      var c = new THREE.Color(arr[i]);
      data[i*4]=Math.round(c.r*255); data[i*4+1]=Math.round(c.g*255);
      data[i*4+2]=Math.round(c.b*255); data[i*4+3]=255;
    }
    var tex = new THREE.DataTexture(data, w, 1, THREE.RGBAFormat);
    tex.magFilter = THREE.LinearFilter; tex.minFilter = THREE.LinearFilter;
    tex.wrapS = THREE.ClampToEdgeWrapping; tex.wrapT = THREE.ClampToEdgeWrapping;
    tex.generateMipmaps = false; tex.needsUpdate = true;
    return tex;
  }

  var fboOpts = function() {
    var isIOS = /(iPad|iPhone|iPod)/i.test(navigator.userAgent);
    return {
      type: isIOS ? THREE.HalfFloatType : THREE.FloatType,
      depthBuffer:false, stencilBuffer:false,
      minFilter:THREE.LinearFilter, magFilter:THREE.LinearFilter,
      wrapS:THREE.ClampToEdgeWrapping, wrapT:THREE.ClampToEdgeWrapping
    };
  };

  /* ── ShaderPass ── */
  function ShaderPass(props) {
    this.props = props||{};
    this.uniforms = (this.props.material||{}).uniforms;
    this.scene = new THREE.Scene();
    this.camera = new THREE.Camera();
    if (this.uniforms) {
      this.material = new THREE.RawShaderMaterial(this.props.material);
      this.plane = new THREE.Mesh(new THREE.PlaneGeometry(2,2), this.material);
      this.scene.add(this.plane);
    }
  }
  ShaderPass.prototype.render = function(renderer) {
    renderer.setRenderTarget(this.props.output||null);
    renderer.render(this.scene, this.camera);
    renderer.setRenderTarget(null);
  };

  /* ── mount ── */
  function mountLiquidEther(container, opts) {
    if (!container) return null;
    opts = opts||{};

    var mouseForce   = opts.mouseForce   != null ? opts.mouseForce   : 14;
    var cursorSize   = opts.cursorSize   != null ? opts.cursorSize   : 80;
    var isViscous    = opts.isViscous    != null ? opts.isViscous    : false;
    var viscous      = opts.viscous      != null ? opts.viscous      : 10;
    var isBounce     = opts.isBounce     != null ? opts.isBounce     : false;
    var resolution   = opts.resolution   != null ? opts.resolution   : 0.5;
    var dtVal        = opts.dt           != null ? opts.dt           : 0.014;
    var BFECC        = opts.BFECC        != null ? opts.BFECC        : true;
    var iterPoisson  = opts.iterationsPoisson != null ? opts.iterationsPoisson : 32;
    var iterViscous  = opts.iterationsViscous != null ? opts.iterationsViscous : 32;
    var colors       = opts.colors       || ['#5227FF','#FF9FFC','#B497CF'];
    var autoDemo     = opts.autoDemo     != null ? opts.autoDemo     : true;
    var autoSpeed    = opts.autoSpeed    != null ? opts.autoSpeed    : 0.5;
    var autoIntensity= opts.autoIntensity!= null ? opts.autoIntensity: 2.2;
    var autoResumeDelay = opts.autoResumeDelay != null ? opts.autoResumeDelay : 1000;
    var autoRampDuration = opts.autoRampDuration != null ? opts.autoRampDuration : 0.6;

    container.classList.add('aurora-container');
    container.style.position = container.style.position || 'relative';
    container.style.overflow = 'hidden';

    var paletteTex = makePalette(colors);
    var bgVec4 = new THREE.Vector4(0,0,0,0);

    /* renderer */
    var pixelRatio = Math.min(window.devicePixelRatio||1, 2);
    var W = Math.max(1, container.offsetWidth);
    var H = Math.max(1, container.offsetHeight);

    var renderer = new THREE.WebGLRenderer({ antialias:true, alpha:true });
    renderer.autoClear = false;
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(W, H);
    var canvas = renderer.domElement;
    canvas.style.width='100%'; canvas.style.height='100%'; canvas.style.display='block';
    container.appendChild(canvas);

    var clock = new THREE.Clock(); clock.start();
    var cTime = 0;

    /* FBO sizes */
    var fW, fH, cellScale, boundarySpace;
    function calcSize() {
      W = Math.max(1, container.offsetWidth);
      H = Math.max(1, container.offsetHeight);
      fW = Math.max(1, Math.round(resolution*W));
      fH = Math.max(1, Math.round(resolution*H));
      cellScale = new THREE.Vector2(1/fW, 1/fH);
      boundarySpace = new THREE.Vector2(1/fW, 1/fH);
    }
    calcSize();

    /* FBOs */
    var fo = fboOpts();
    function makeFBO() { return new THREE.WebGLRenderTarget(fW, fH, fo); }
    var vel0=makeFBO(), vel1=makeFBO(), velV0=makeFBO(), velV1=makeFBO();
    var divFBO=makeFBO(), press0=makeFBO(), press1=makeFBO();

    /* Advection */
    var advUniforms = {
      boundarySpace:{value:cellScale}, px:{value:cellScale}, fboSize:{value:new THREE.Vector2(fW,fH)},
      velocity:{value:vel0.texture}, dt:{value:dtVal}, isBFECC:{value:BFECC}
    };
    var advPass = new ShaderPass({material:{vertexShader:face_vert,fragmentShader:advection_frag,uniforms:advUniforms},output:vel1});
    // boundary lines
    var bVerts = new Float32Array([-1,-1,0,-1,1,0,-1,1,0,1,1,0,1,1,0,1,-1,0,1,-1,0,-1,-1,0]);
    var bGeo = new THREE.BufferGeometry(); bGeo.setAttribute('position', new THREE.BufferAttribute(bVerts,3));
    var bMat = new THREE.RawShaderMaterial({vertexShader:line_vert,fragmentShader:advection_frag,uniforms:advUniforms});
    var bLine = new THREE.LineSegments(bGeo, bMat);
    advPass.scene.add(bLine);

    /* External force */
    var efScene = new THREE.Scene(), efCamera = new THREE.Camera();
    var efUniforms = {
      px:{value:cellScale}, force:{value:new THREE.Vector2()},
      center:{value:new THREE.Vector2()}, scale:{value:new THREE.Vector2(cursorSize,cursorSize)}
    };
    var efMat = new THREE.RawShaderMaterial({vertexShader:mouse_vert,fragmentShader:externalForce_frag,
      blending:THREE.AdditiveBlending, depthWrite:false, uniforms:efUniforms});
    var efMesh = new THREE.Mesh(new THREE.PlaneGeometry(1,1), efMat);
    efScene.add(efMesh);

    /* Viscous */
    var visUniforms = {
      boundarySpace:{value:boundarySpace}, velocity:{value:vel1.texture},
      velocity_new:{value:velV0.texture}, v:{value:viscous}, px:{value:cellScale}, dt:{value:dtVal}
    };
    var visPass = new ShaderPass({material:{vertexShader:face_vert,fragmentShader:viscous_frag,uniforms:visUniforms},output:velV1});

    /* Divergence */
    var divUniforms = {
      boundarySpace:{value:boundarySpace}, velocity:{value:velV0.texture},
      px:{value:cellScale}, dt:{value:dtVal}
    };
    var divPass = new ShaderPass({material:{vertexShader:face_vert,fragmentShader:divergence_frag,uniforms:divUniforms},output:divFBO});

    /* Poisson */
    var poisUniforms = {
      boundarySpace:{value:boundarySpace}, pressure:{value:press0.texture},
      divergence:{value:divFBO.texture}, px:{value:cellScale}
    };
    var poisPass = new ShaderPass({material:{vertexShader:face_vert,fragmentShader:poisson_frag,uniforms:poisUniforms},output:press1});

    /* Pressure */
    var pressUniforms = {
      boundarySpace:{value:boundarySpace}, pressure:{value:press0.texture},
      velocity:{value:velV0.texture}, px:{value:cellScale}, dt:{value:dtVal}
    };
    var pressPass = new ShaderPass({material:{vertexShader:face_vert,fragmentShader:pressure_frag,uniforms:pressUniforms},output:vel0});

    /* Color output */
    var outScene = new THREE.Scene(), outCamera = new THREE.Camera();
    var outMat = new THREE.RawShaderMaterial({
      vertexShader:face_vert, fragmentShader:color_frag, transparent:true, depthWrite:false,
      uniforms:{ velocity:{value:vel0.texture}, boundarySpace:{value:new THREE.Vector2()},
        palette:{value:paletteTex}, bgColor:{value:bgVec4} }
    });
    outScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2), outMat));

    /* Mouse tracking */
    var mCoords = new THREE.Vector2(), mOld = new THREE.Vector2(), mDiff = new THREE.Vector2();
    var mMoved = false, mTimer = null, mHover = false, mHasUser = false;
    var mAutoActive = false;

    function onMouseMove(e) {
      var rect = container.getBoundingClientRect();
      if (rect.width===0||rect.height===0) return;
      var cx=e.clientX, cy=e.clientY;
      mHover = cx>=rect.left&&cx<=rect.right&&cy>=rect.top&&cy<=rect.bottom;
      if (!mHover) return;
      lastUserTime = performance.now();
      if (mAutoActive && !mHasUser) { mHasUser=true; mAutoActive=false; }
      var nx=(cx-rect.left)/rect.width, ny=(cy-rect.top)/rect.height;
      mCoords.set(nx*2-1, -(ny*2-1));
      mMoved = true;
      if (mTimer) clearTimeout(mTimer);
      mTimer = setTimeout(function(){mMoved=false;},100);
      mHasUser = true;
    }
    function onTouchMove(e) {
      if (e.touches.length!==1) return;
      var t=e.touches[0];
      onMouseMove({clientX:t.clientX, clientY:t.clientY});
    }
    function onMouseLeave() { mHover=false; }

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('touchmove', onTouchMove, {passive:true});
    document.addEventListener('mouseleave', onMouseLeave);

    /* Auto driver */
    var lastUserTime = performance.now();
    var autoActive = false, autoCurrent = new THREE.Vector2(), autoTarget = new THREE.Vector2();
    var autoLastTime = performance.now(), autoActivationTime = 0;
    function pickTarget() { autoTarget.set((Math.random()*2-1)*0.8, (Math.random()*2-1)*0.8); }
    pickTarget();

    function updateAuto() {
      if (!autoDemo) return;
      var now = performance.now();
      if (now - lastUserTime < autoResumeDelay) { if(autoActive){autoActive=false;mAutoActive=false;} return; }
      if (mHover) { if(autoActive){autoActive=false;mAutoActive=false;} return; }
      if (!autoActive) { autoActive=true; autoCurrent.copy(mCoords); autoLastTime=now; autoActivationTime=now; }
      mAutoActive = true;
      var dt2 = (now-autoLastTime)/1000; autoLastTime=now;
      if (dt2>0.2) dt2=0.016;
      var dir = autoTarget.clone().sub(autoCurrent);
      var dist = dir.length();
      if (dist<0.01) { pickTarget(); return; }
      dir.normalize();
      var ramp = 1;
      if (autoRampDuration>0) { var t=Math.min(1,(now-autoActivationTime)/(autoRampDuration*1000)); ramp=t*t*(3-2*t); }
      var move = Math.min(autoSpeed*dt2*ramp, dist);
      autoCurrent.addScaledVector(dir, move);
      mCoords.set(autoCurrent.x, autoCurrent.y);
      mMoved = true;
    }

    /* Resize */
    function onResize() {
      W = Math.max(1, container.offsetWidth);
      H = Math.max(1, container.offsetHeight);
      renderer.setSize(W, H, false);
      calcSize();
      [vel0,vel1,velV0,velV1,divFBO,press0,press1].forEach(function(f){f.setSize(fW,fH);});
      advUniforms.fboSize.value.set(fW,fH);
    }
    window.addEventListener('resize', onResize);

    /* Simulation step */
    function simulate() {
      if (isBounce) boundarySpace.set(0,0); else boundarySpace.copy(cellScale);

      // Advection
      advUniforms.dt.value = dtVal;
      bLine.visible = isBounce;
      advUniforms.isBFECC.value = BFECC;
      advPass.render(renderer);

      // External force
      mDiff.subVectors(mCoords, mOld);
      mOld.copy(mCoords);
      if (mOld.x===0&&mOld.y===0) mDiff.set(0,0);
      if (mAutoActive) mDiff.multiplyScalar(autoIntensity);

      var fx = (mDiff.x/2)*mouseForce, fy = (mDiff.y/2)*mouseForce;
      var csx = cursorSize*cellScale.x, csy = cursorSize*cellScale.y;
      efUniforms.force.value.set(fx, fy);
      efUniforms.center.value.set(
        Math.min(Math.max(mCoords.x, -1+csx+cellScale.x*2), 1-csx-cellScale.x*2),
        Math.min(Math.max(mCoords.y, -1+csy+cellScale.y*2), 1-csy-cellScale.y*2)
      );
      efUniforms.scale.value.set(cursorSize, cursorSize);
      renderer.setRenderTarget(vel1);
      renderer.render(efScene, efCamera);
      renderer.setRenderTarget(null);

      // Viscous
      var vel = vel1;
      if (isViscous) {
        var fIn, fOut;
        for (var i=0;i<iterViscous;i++) {
          fIn = (i%2===0)?velV0:velV1; fOut = (i%2===0)?velV1:velV0;
          visUniforms.velocity_new.value = fIn.texture;
          visPass.props.output = fOut;
          visPass.render(renderer);
        }
        vel = fOut||velV0;
      }

      // Divergence
      divUniforms.velocity.value = vel.texture;
      divPass.render(renderer);

      // Poisson
      var pOut;
      for (var j=0;j<iterPoisson;j++) {
        var pIn = (j%2===0)?press0:press1; pOut = (j%2===0)?press1:press0;
        poisUniforms.pressure.value = pIn.texture;
        poisPass.props.output = pOut;
        poisPass.render(renderer);
      }

      // Pressure
      pressUniforms.velocity.value = vel.texture;
      pressUniforms.pressure.value = (pOut||press0).texture;
      pressPass.render(renderer);
    }

    /* Render loop */
    var raf = 0, running = true;
    function loop() {
      if (!running) return;
      cTime += clock.getDelta();
      updateAuto();
      simulate();
      // Color output
      renderer.setRenderTarget(null);
      renderer.render(outScene, outCamera);
      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);

    console.log('[LiquidEther] Mounted successfully');

    return {
      update: function(newOpts) {
        if (!newOpts) return;
        if (newOpts.colors) { paletteTex = makePalette(newOpts.colors); outMat.uniforms.palette.value = paletteTex; }
        if (newOpts.mouseForce != null) mouseForce = newOpts.mouseForce;
        if (newOpts.cursorSize != null) cursorSize = newOpts.cursorSize;
        if (newOpts.autoSpeed != null) autoSpeed = newOpts.autoSpeed;
        if (newOpts.autoIntensity != null) autoIntensity = newOpts.autoIntensity;
      },
      destroy: function() {
        running = false;
        cancelAnimationFrame(raf);
        window.removeEventListener('resize', onResize);
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('touchmove', onTouchMove);
        document.removeEventListener('mouseleave', onMouseLeave);
        if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
        renderer.dispose(); renderer.forceContextLoss();
      }
    };
  }

  window.Aurora = { mount: mountLiquidEther };
  console.log('[LiquidEther] Module loaded');
})();
