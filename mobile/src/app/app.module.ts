import { HttpClientModule } from '@angular/common/http';
import { StatusBar } from '@ionic-native/status-bar';
import { SplashScreen } from '@ionic-native/splash-screen';
import { BrowserModule } from '@angular/platform-browser';
import { ErrorHandler, NgModule } from '@angular/core';
import { IonicApp, IonicErrorHandler, IonicModule } from 'ionic-angular';

import { MyAppComponent } from './app.component';
import { TodayComponent } from '../pages/today/today.component';
import { ListComponent } from '../pages/list/list';
import { AuthServiceProvider } from '../providers/auth-service/auth-service';
import { httpInterceptorProviders } from '../http-interceptors';
import { StylistServiceProvider } from '../providers/stylist-service/stylist-service';

@NgModule({
  declarations: [
    MyAppComponent,
    TodayComponent,
    ListComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    IonicModule.forRoot(MyAppComponent)
  ],
  bootstrap: [IonicApp],
  entryComponents: [
    MyAppComponent,
    TodayComponent,
    ListComponent
  ],
  providers: [
    StatusBar,
    SplashScreen,
    {provide: ErrorHandler, useClass: IonicErrorHandler},
    AuthServiceProvider,
    StylistServiceProvider,
    httpInterceptorProviders
  ]
})
export class AppModule {}
