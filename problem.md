# decompole and compile
* use ildasm to decompile
    * ildasm Assembly-CSharp.dll /output:pop.il
* use ilasm to compile
    * ilasm pop.il /output:Assembly-CSharp.dll
* we must change inf to (00 00 f0 7f), -inf to (00 00 f0 ff), maybe there is a better way to solve this, like use the compatible version
* use ilspy to decompile will cause more problems
* seems there are codes outside of Assembly-CSharp.dll, like UnityEngine.dll, we can use ilasm to compile them too
* 其他的文本存在于资源，绝大多数的TextMashPro和Text组件中，需要解包资源文件，修改后重新打包

# font
* 主要使用TMP，而且可能不止一个字体？
* 尝试从头做一次，看看是否还是会出现这些问题
* 同样也使用了其他字体，可能是unity原生text，不清楚是哪个
* 目前完成了LiberationSans的TMP字体替换，但仍存在一些问题如：
    * 部分文字直接不显示
    * 不分文字显示为紫色色块

* TMP字体替换注意事项：
    * 注意保证版本一致
    * 需要替换MonoBehaviour和Atlas 2DTexture
    * Material文件暂时可能没必要替换
    * PathID一般需要保持一致，GUID和hashCode不确定，但如果出问题可以修改
    * 生成字体时自动设置大小即可
    * 可能要考虑字库大小，否则贴图字体可能过大
    * 原项目中underlay（也就是shadow）的偏移值过大，导致直接替换字体后阴影十分混乱，需要手动调整LiberationSans SDF - Drop Shadow的对应偏移值